from pathlib import Path
import pexpect
from shutil import which
from .simulation_heuristics import UserChoice


class PyXmvError(Exception):
    errs = (
        "No trace: constraint and initial state are inconsistent",
        "illegal operand types",
        "Type System Violation detected",
        "Nested next operator.")

    @classmethod
    def factory(cls, msg):
        err_lines = [
            line for line in msg.splitlines()
            if any(err in line for err in cls.errs)]
        if err_lines:
            raise PyXmvError("\n".join(err_lines))


class PyXmvTimeout(PyXmvError):
    pass


class NuXmvInt:
    PROMPT = "nuXmv > "
    STATE_SEP = "================= State ================="

    def __init__(self):
        if which("nuxmv") is None:
            raise FileNotFoundError("nuxmv not in PATH")
        self.nuxmv = pexpect.spawn("nuxmv -int", encoding="utf-8")
        self.expect_prompt()

    def expect_prompt(self, timeout: int | None = None) -> int:
        try:
            return self.nuxmv.expect_exact(
                NuXmvInt.PROMPT, timeout=timeout,
                searchwindowsize=2*len(NuXmvInt.PROMPT))
        except pexpect.TIMEOUT:
            self.nuxmv.sendcontrol("c")
            raise PyXmvTimeout()

    def expect(self, prompts: list[str], timeout: int | None = None):
        print("xxx")
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

    def __del__(self):
        self.nuxmv.kill(9)

    def msat_setup(self, fname: Path, shown_states: int = 65535) -> None:
        cmds = (
            "reset",
            f"set shown_states {shown_states}",
            f"set input_file {fname}",
            "go_msat")
        for cmd in cmds:
            self.nuxmv.sendline(cmd)
            self.expect_prompt()
            PyXmvError.factory(self.nuxmv.before)

    def init(self, h, c: str | None = "TRUE", timeout: int | None = None):
        self.nuxmv.sendline(f"""msat_pick_state -c "{c}" -v -i""")
        output = self.get_output(timeout=timeout, prompts=[
            r"Choose a state from the above \(0-[0-9]+\): ",
            "There's only one available state. Press Return to Proceed."])
        print(output)
        states = output.split(NuXmvInt.STATE_SEP)[1:]
        choice = h.choose_from(states)
        self.nuxmv.sendline(str(choice))
        return self.get_output(timeout)

    def ic3(self, ltlspec: str | None = None, timeout: int | None = None) -> str:  # noqa: E501
        ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        self.nuxmv.sendline(f"check_ltlspec_ic3 {ltlspec}")
        return self.get_output(timeout)

    def ic3_invar(self, ltlspec: str | None = None, timeout: int | None = None) -> str:  # noqa: E501
        ltlspec = f"""-L "{ltlspec}" """ if ltlspec else ""
        self.nuxmv.sendline(f"check_property_as_invar_ic3 {ltlspec}")
        return self.get_output(timeout)

    def bmc(self, bound: int, ltlspec: str | None = None, timeout: int | None = None) -> str:  # noqa: E501
        ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        self.nuxmv.sendline(f"msat_check_ltlspec-bmc -k {bound} {ltlspec}")
        return self.get_output(timeout)

    def reset(self) -> None:
        self.nuxmv.sendline("reset")
        self.expect_prompt()

    def get_successor_states(self, c: str = "TRUE") -> list[str]:
        self.nuxmv.sendline(f"msat_simulate -i -a -k 1 -c {c}")
        self.nuxmv.expect([
            r"Choose a state from the above \(0-[0-9]+\): ",
            "There's only one available state. Press Return to Proceed."])
        print(self.nuxmv.before)
        return self.nuxmv.before.split(NuXmvInt.STATE_SEP)[1:]

    def simulate(self, steps=1, c: str = "TRUE", heuristic=None) -> None:  # noqa: E501
        h = UserChoice() if heuristic is None else heuristic
        for _ in range(steps):
            self.nuxmv.sendline(f"msat_simulate -i -a -k 1 -c {c}")
            self.nuxmv.expect([
                r"Choose a state from the above \(0-[0-9]+\): ",
                "There's only one available state. Press Return to Proceed."
            ])
            print(self.nuxmv.before)
            states = self.get_successor_states(c)
            choice = h.choose_from(states)
            self.nuxmv.sendline(str(choice))
            self.expect_prompt()
            print(self.nuxmv.before)