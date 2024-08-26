from collections.abc import Callable, Sequence
from functools import wraps
from pathlib import Path
from shutil import which
import re

import pexpect

from .simulation_heuristics import UserChoice

re_state = re.compile(r"[0-9]+\) -------------------------")


class PyXmvError(Exception):
    errs = (
        "illegal operand types",
        "Nested next operator",
        "No trace: constraint and initial state are inconsistent",
        "not well typed"
        "TYPE ERROR",
        "Type System Violation detected",
        "unexpected expression encountered during parsing")

    @classmethod
    def factory(cls, msg):
        if "The boolean model must be built before." in msg:
            raise NoBooleanModel(msg.strip())
        err_lines = [
            line for line in msg.splitlines()
            if any(err in line for err in cls.errs)]
        if err_lines:
            raise PyXmvError("\n".join(err_lines))


class NoBooleanModel(PyXmvError):
    pass


class PyXmvTimeout(PyXmvError):
    pass


class NuXmvInt:
    PROMPT = "nuXmv > "
    STATE_SEP = "================= State ================="
    AVAIL_STATES = "***************  AVAILABLE STATES  *************"

    def __init__(self):
        self.nuxmv = None
        if which("nuxmv") is None:
            raise FileNotFoundError("nuxmv not in PATH")
        self.nuxmv = pexpect.spawn("nuxmv", ["-int"], encoding="utf-8")
        self.nuxmv.setecho(False)
        self.expect_prompt()

    def __del__(self):
        if self.nuxmv is not None:
            self.nuxmv.kill(9)

    def send_and_expect(self, cmd: str) -> None:
        self.nuxmv.sendline(cmd)
        self.nuxmv.expect_exact(cmd)

    def expect_prompt(self, timeout: int | None = None) -> int:
        try:
            return self.nuxmv.expect_exact(
                NuXmvInt.PROMPT, timeout=timeout,
                searchwindowsize=2*len(NuXmvInt.PROMPT))
        except pexpect.TIMEOUT:
            self.nuxmv.sendcontrol("c")
            raise PyXmvTimeout()

    def expect(self, prompts: list[str], timeout: int | None = None):
        try:
            self.nuxmv.expect(prompts, timeout)
        except pexpect.TIMEOUT:
            self.nuxmv.sendcontrol("c")
            raise PyXmvTimeout()

    def get_output(self, timeout: int | None = None, prompts: list[str] | None = None) -> str:  # noqa: E501
        if prompts is None:
            self.expect_prompt(timeout)
        else:
            self.expect(prompts, timeout)
        PyXmvError.factory(self.nuxmv.before)
        return self.nuxmv.before

    @staticmethod
    def nuxmv_cmd(func: Callable[..., tuple[str, int | None]]):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            cmd, timeout = func(self, *args, **kwargs)
            try:
                self.send_and_expect(cmd)
                return self.get_output(timeout)
            except NoBooleanModel:
                self.send_and_expect("build_boolean_model")
                self.expect_prompt()
                self.send_and_expect(cmd)
                return self.get_output(timeout)
        return wrapper

    def msat_setup(self, fname: Path, shown_states: int = 65535) -> None:
        """Set up nuXmv for symbolic procedures."""

        cmds = (
            "reset",
            f"set shown_states {shown_states}",
            f"set input_file {fname}",
            "go_msat")
        for cmd in cmds:
            self.nuxmv.sendline(cmd)
            self.expect_prompt()
            PyXmvError.factory(self.nuxmv.before)

    def init(self, h, c: str | None = "TRUE", timeout: int | None = None) -> str:  # noqa: E501
        self.send_and_expect(f"""msat_pick_state -c "{c}" -v -i""")
        output = self.get_output(timeout=timeout, prompts=[
            r"Choose a state from the above \(0-[0-9]+\): ",
            "There's only one available state. Press Return to Proceed."])
        states = output.split(NuXmvInt.STATE_SEP)[1:]
        choice = h.choose_from(states)
        chosen = re.sub(re_state, "", states[choice], 1).strip()
        self.send_and_expect(str(choice))
        self.get_output(timeout)
        return chosen

    @nuxmv_cmd
    def ic3(self, bound: int | None = None, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        fmt_bound = f"-k {bound}" if bound else ""
        fmt_ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        return (f"check_ltlspec_ic3 {fmt_bound} {fmt_ltlspec}"), timeout

    @nuxmv_cmd
    def ic3_invar(self, bound: int | None = None, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        fmt_bound = f"-k {bound}" if bound else ""
        fmt_ltlspec = f"""-L "{ltlspec}" """ if ltlspec else ""
        return f"check_property_as_invar_ic3 {fmt_bound} {fmt_ltlspec}", timeout  # noqa: E501

    @nuxmv_cmd
    def bmc(self, bound: int, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        return f"msat_check_ltlspec_bmc -k {bound} {ltlspec}", timeout

    @nuxmv_cmd
    def reset(self) -> tuple[str, None]:
        return "reset", None

    def get_successor_states(self, c: str = "TRUE") -> list[str]:
        self.nuxmv.sendline(f"msat_simulate -i -a -k 1 -c {c}")
        self.nuxmv.expect([
            r"Choose a state from the above \(0-[0-9]+\): ",
            "There's only one available state. Press Return to Proceed."])
        return self.nuxmv.before.split(NuXmvInt.STATE_SEP)[1:]

    def simulate(self, steps=1, c: str = "TRUE", heuristic=None) -> tuple[Sequence[str], bool]:  # noqa: E501
        h = UserChoice() if heuristic is None else heuristic
        result = []
        for _ in range(steps):
            states = self.get_successor_states(c)
            choice = h.choose_from(states)
            chosen = re.sub(re_state, "", states[choice], 1).strip()
            result.append(chosen)
            self.send_and_expect(str(choice))
            self.expect_prompt()
            is_sat = "Simulation is SAT" in self.nuxmv.before
            if not is_sat:
                break
        return result, is_sat
