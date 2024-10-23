from collections.abc import Callable, Sequence
from functools import wraps
from shutil import which
import re

import pexpect

from .simulation_heuristics import UserChoice, SimulationHeuristic
from .utils import PathLike

re_state = re.compile(r"[0-9]+\) -------------------------")


class PyXmvError(Exception):
    errs = (
        "A model must be read before",
        "A starting state has to be chosen"
        "An integer was expected",
        "illegal operand types",
        "Impossible to build a BDD FSM with infinite precision variables",
        "Nested next operator",
        "No trace: constraint and initial state are inconsistent",
        "not well typed",
        "SMT model not built"
        "TYPE ERROR",
        "Type System Violation detected",
        "undefined",
        "unexpected expression encountered during parsing")

    @classmethod
    def factory(cls, msg):
        if "The boolean model must be built before." in msg:
            raise NoBooleanModel(msg.strip())
        if "You must set the input file before." in msg:
            raise NoInputFile(msg.strip())
        err_lines = [
            line for line in msg.splitlines()
            if any(err in line for err in cls.errs)]
        if err_lines:
            raise PyXmvError("\n".join(err_lines))


class NoBooleanModel(PyXmvError):
    pass


class NoInputFile(PyXmvError):
    pass


class PyXmvTimeout(PyXmvError):
    pass


class PyXmv:
    PROMPT = "nuXmv > "
    STATE_SEP = "================= State ================="
    AVAIL_STATES = "***************  AVAILABLE STATES  *************"

    def __init__(self, fname: PathLike | None = None):
        self.go_called = False
        self.go_msat_called = False
        if which("nuxmv") is None:
            raise FileNotFoundError("nuxmv not in PATH")
        self.nuxmv = pexpect.spawn("nuxmv", ["-int"], encoding="utf-8")
        self.nuxmv.setecho(False)
        self.expect_prompt()
        self.default_env = self.get_env()
        self.env = {**self.default_env}
        if fname:
            self.update_env("input_file", fname)

    def __del__(self):
        if self.nuxmv is not None:
            self.nuxmv.kill(9)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__del__()

    def send_and_expect(self, cmd: str) -> None:
        cmd = cmd.strip()
        try:
            self.nuxmv.sendline(cmd)
        except IOError:
            raise PyXmvError("The nuxmv instance has been terminated.")
        self.nuxmv.expect_exact(cmd)

    def expect_prompt(self, timeout: int | None = None) -> int:
        try:
            return self.nuxmv.expect_exact(
                PyXmv.PROMPT, timeout=timeout,
                searchwindowsize=2*len(PyXmv.PROMPT))
        except pexpect.TIMEOUT:
            self.nuxmv.sendcontrol("c")
            raise PyXmvTimeout()

    def expect(self, prompts: list, timeout: int | None = None):
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
        return self.nuxmv.before or ""

    @staticmethod
    def nuxmv_cmd(*, bdd: bool = False, msat: bool = False):
        def nuxmv_cmd_inner(func: Callable[..., tuple[str, int | None]]):
            """Decorator that invokes a nuXmv command provided by the decorated
            function."""
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                if bdd and not self.go_called:
                    self.go()
                elif msat and not self.go_msat_called:
                    self.go_msat()
                cmd, timeout, *prompts = func(self, *args, **kwargs)
                try:
                    self.send_and_expect(cmd)
                    return self.get_output(timeout, prompts or None)
                except NoBooleanModel:
                    self.send_and_expect("build_boolean_model")
                    self.expect_prompt()
                    self.send_and_expect(cmd)
                    return self.get_output(timeout)
            return wrapper
        return nuxmv_cmd_inner

    @nuxmv_cmd()
    def raw(self, cmd: str, timeout: int | None = None, prompts: list[str] | None = None):  # noqa: E501
        """Send a raw command to NuXmv."""
        return (cmd, timeout, *prompts) if prompts else cmd, timeout

    def update_env(self, name: str, value: PathLike | int | float | None) -> None:  # noqa: E501
        """Update an environment variable."""
        self.raw(f"unset {name}" if value is None else f'set {name} "{value}"')
        self.env[name] = str(value)

    def get_env(self) -> dict[str, str]:
        """Return the current nuXmv environment."""
        out = self.raw("set")
        result = {}
        for line in out.splitlines():
            line = line.strip()
            if line:
                name, value = line.split(maxsplit=2)
                if value == "NULL":
                    value = None
                elif value.startswith('"'):
                    value = value[1:-1]
                result[name] = value
        return result

    def go_msat(self):
        """Set up nuXmv for symbolic procedures."""
        self.raw("go_msat")
        self.go_msat_called = True

    def go(self):
        """Set up NuXmv for BDD-based procedures."""
        self.raw("go")
        self.go_called = True

    def init_simulation(self, h: SimulationHeuristic, c: str | None = "TRUE", timeout: int | None = None) -> str:  # noqa: E501
        output = self.msat_pick_state(c, True, timeout)
        states = output.split(PyXmv.STATE_SEP)[1:]
        choice = h.choose_from(states)
        chosen = re.sub(re_state, "", states[choice], 1).strip()
        self.raw(str(choice), timeout)
        return chosen

    @nuxmv_cmd(bdd=True)
    def check_ltlspec(self, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        """Perform BDD-based symbolic model checking."""
        fmt_ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        return f"check_ltlspec {fmt_ltlspec}", timeout

    @nuxmv_cmd(msat=True)
    def check_ltlspec_ic3(self, bound: int | None = None, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        """Perform symbolic model checking with IC3."""
        fmt_bound = f"-k {bound}" if bound else ""
        fmt_ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        return f"check_ltlspec_ic3 {fmt_bound} {fmt_ltlspec}", timeout

    @nuxmv_cmd(msat=True)
    def check_property_as_invar_ic3(self, bound: int | None = None, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        """Perform invariant checking with IC3."""
        fmt_bound = f"-k {bound}" if bound else ""
        fmt_ltlspec = f"""-L "{ltlspec}" """ if ltlspec else ""
        return f"check_property_as_invar_ic3 {fmt_bound} {fmt_ltlspec}", timeout  # noqa: E501

    @nuxmv_cmd(msat=True)
    def msat_check_ltlspec_bmc(self, bound: int, ltlspec: str | None = None, timeout: int | None = None) -> tuple[str, int | None]:  # noqa: E501
        """Perform symbolic bounded model checking."""
        ltlspec = f"""-p "{ltlspec}" """ if ltlspec else ""
        return f"msat_check_ltlspec_bmc -k {bound} {ltlspec}", timeout

    @nuxmv_cmd(msat=True)
    def msat_pick_state(self, c: str = "TRUE", i: bool = False, timeout: int | None = None) -> tuple:  # noqa: E501
        """Pick a feasible initial state.

        **Warning**: When `i = True` the function is blocking!

        Args:
            c (str, optional): Additional constraint on the state. Defaults to "TRUE".
            i (bool, optional): Interactive. Defaults to False.
            timeout (int | None, optional): timeout in seconds. Defaults to None.
        """
        return (
            f"""msat_pick_state -c "{c}" -v -i""",
            timeout,
            r"Choose a state from the above \(0-[0-9]+\): ",
            "There's only one available state. Press Return to Proceed."
        ) if i else (
            f"""msat_pick_state -c "{c}" -v""",
            timeout)

    @nuxmv_cmd(msat=True)
    def msat_simulate(self, c: str = "TRUE", i: bool = False, k: int = 1, timeout: int | None = None) -> tuple:  # noqa: E501
        """Extend a (SMT-based) simulation.

        **Warnings**
            `msat_pick_state` has to be called before the 1st call to `msat_simulate`.
            When `i = True` the function is blocking, and only supports `k=1`.

        Args:
            c (str, optional): Additional constraint on the state. Defaults to "TRUE".
            i (bool, optional): Interactive. Defaults to False.
            k (int, optional): How many steps to simulate. Defaults to 1.
            timeout (int | None, optional): timeout in seconds. Defaults to None.

        Raises:
            PyXmvError: Raised when k>1 in interactive mode.
        """
        if k > 1 and i:
            raise PyXmvError("msat_simulate -i does not support k > 1.")
        return (
            f"""msat_simulate -i -c "{c}" -a -k {k}""",
            timeout,
            r"Choose a state from the above \(0-[0-9]+\): ",
            "There's only one available state. Press Return to Proceed."
        ) if i else (
            f"""msat_simulate -c "{c}" -a -k {k}""",
            timeout)

    @nuxmv_cmd()
    def reset(self, reset_env: bool = False) -> tuple[str, None]:
        """Reset the state of nuXmv and pyXmv."""
        self.go_called = False
        self.go_msat_called = False
        if reset_env:
            for name, value in self.default_env.items():
                self.update_env(name, value)
        return "reset", None

    def get_successor_states(self, c: str = "TRUE") -> list[str]:
        """Get successors to the current state in a simulation."""
        output = self.msat_simulate(c, i=True)
        return (output or "").split(PyXmv.STATE_SEP)[1:]

    def run_simulation(self, steps=1, c: str = "TRUE", heuristic=None) -> tuple[Sequence[str], bool]:  # noqa: E501
        """Simulate a nuXmv system."""
        h = UserChoice() if heuristic is None else heuristic
        result = []
        for _ in range(steps):
            states = self.get_successor_states(c)
            choice = h.choose_from(states)
            chosen = re.sub(re_state, "", states[choice], 1).strip()
            result.append(chosen)
            self.raw(str(choice))
            is_sat = "Simulation is SAT" in (self.nuxmv.before or "")
            if not is_sat:
                break
        return result, is_sat
