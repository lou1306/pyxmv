import pexpect
from shutil import which
from .simulation_heuristics import UserChoice


class NuXmvError(Exception):
    NO_TRACE = "No trace: constraint and initial state are inconsistent"
    ILLEGAL_OP = "illegal operand types"
    TYPE_SYSTEM_VIOLATION = "Type System Violation detected"

    @classmethod
    def factory(cls, msg):
        err_lines = [
            line for line in msg.splitlines()
            if cls.NO_TRACE in line
            or cls.ILLEGAL_OP in line
            or cls.TYPE_SYSTEM_VIOLATION in line]
        if err_lines:
            raise NuXmvError("\n".join(err_lines))


class NuXmvInt:
    PROMPT = "nuXmv > "
    STATE_SEP = "================= State ================="

    def __init__(self):
        if which("nuxmv") is None:
            raise FileNotFoundError("nuxmv not in PATH")
        self.nuxmv = pexpect.spawn("nuxmv -int", encoding="utf-8")
        self.expect_prompt()

    def expect_prompt(self, timeout=None) -> int:
        return self.nuxmv.expect_exact(NuXmvInt.PROMPT, timeout=timeout)

    def __del__(self):
        self.nuxmv.kill(9)

    def msat_setup(self, fname):
        cmds = (
            "reset",
            "set shown_states 65535",
            f"set input_file {fname}",
            "go_msat")
        for cmd in cmds:
            self.nuxmv.sendline(cmd)
            self.expect_prompt()
            NuXmvError.factory(self.nuxmv.before)

    def init(self, c="TRUE"):
        self.nuxmv.sendline(f"""msat_pick_state -c "{c}" -v""")
        self.expect_prompt()
        return self.nuxmv.before

    def ic3(self):
        self.nuxmv.sendline("check_ltlspec_ic3")
        self.expect_prompt()
        return self.nuxmv.before

    def ic3_invar(self):
        self.nuxmv.sendline("check_property_as_invar_ic3")
        self.expect_prompt()
        return self.nuxmv.before

    def bmc(self, bound):
        self.nuxmv.sendline(f"msat_check_ltlspec-bmc -k {bound}")
        self.expect_prompt()
        return self.nuxmv.before

    def reset(self) -> None:
        self.nuxmv.sendline("reset")
        self.expect_prompt()

    def simulate(self, steps=1, c="TRUE", heuristic=None):
        h = UserChoice() if heuristic is None else heuristic
        for _ in range(steps):
            self.nuxmv.sendline(f"msat_simulate -i -a -k 1 -c {c}")
            self.nuxmv.expect([
                r"Choose a state from the above \(0-[0-9]+\): ",
                "There's only one available state. Press Return to Proceed."
            ])
            print(self.nuxmv.before)
            states = self.nuxmv.before.split(NuXmvInt.STATE_SEP)[1:]
            choice = h.choose_from(states)
            self.nuxmv.sendline(str(choice))
            self.expect_prompt()
            print(self.nuxmv.before)
