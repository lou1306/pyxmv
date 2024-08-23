import importlib.metadata
import signal
import sys
from collections.abc import Callable
from functools import wraps
from sys import exit

import msgspec
import typer

from . import cli
from .nuxmvint import NuXmvInt, PyXmvError, PyXmvTimeout
from .outcome import Outcome, Trace, Verdict

app = typer.Typer(
    pretty_exceptions_show_locals=False,
    rich_markup_mode="markdown")
DEBUG = False


@app.callback()
def callback(debug: cli.Debug = False):
    """
    (Unofficial) Python API and CLI for NuXmv.
    """
    global DEBUG
    DEBUG = debug


@app.command()
def version():
    """ Print version information and exit."""
    try:
        print(importlib.metadata.version("pyxmv"))
    except importlib.metadata.PackageNotFoundError:
        print("This command only works if pyxmv is installed.")
        print("Try 'poetry install'.")
        exit(1)


def dump(obj: Trace | Outcome, fmt: cli.OutputFormat) -> None:
    if fmt == cli.OutputFormat.PLAIN:
        print(*obj.pprint(), sep='\n')
    elif fmt == cli.OutputFormat.JSON:
        obj_dict = obj.as_dict(parse=True)
        if "unparsed" in obj_dict:
            del obj_dict["unparsed"]
        print(msgspec.json.encode(obj_dict).decode())


def dump_states(states, fmt: cli.OutputFormat, err_code: cli.ExitCode) -> None:
    def inner(signum, frame):
        if DEBUG and signum is not None:
            print(f"Caught {signum=} with {frame=}", file=sys.stderr)
        if states:
            trace = Trace.of_states(states, "Simulation", "MSAT Simulation (generated with pyxmv)")  # noqa: E501
            dump(trace, fmt)
            err_code.exit()
    return inner


@app.command()
def simulate(fname: cli.Path,
             steps: cli.Steps = 0,
             seed: cli.Seed = None,
             heuristics: cli.Heuristics = cli.HeuristicsEnum.usr,
             format: cli.OutputFormat = cli.OutputFormat.PLAIN.value):
    """Simulate a nuxmv model."""
    heur = heuristics.get(seed)
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    states = []
    signal.signal(signal.SIGTERM, dump_states(states, cli.ExitCode.TIMEOUT, format))  # noqa: E501
    try:
        states.append(nuxmv.init(h=heur))
        steps = steps or -1
        while steps != 0:
            state, is_sat = nuxmv.simulate(heuristic=heur)
            states.extend(state)
            steps = steps - 1 if steps > 0 else -1
            if not is_sat:
                break
    except KeyboardInterrupt:
        pass
    dump_states(states, cli.ExitCode.SUCCESS, format)(None, None)


def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PyXmvTimeout:
            cli.ExitCode.TIMEOUT.exit("Timeout")
        except PyXmvError as err:
            if DEBUG:
                raise err
            cli.ExitCode.INTERNAL_ERROR.exit(str(err))
    return wrapper


def handle_outcomes(func: Callable[..., tuple[str, cli.OutputFormat]]):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cex, fmt = func(*args, **kwargs)
        fail = False
        inconc = False
        for outcome in Outcome.parse(cex):
            inconc |= outcome.verdict == Verdict.UNKNOWN
            if outcome.verdict == Verdict.FALSE:
                fail = True
                dump(outcome, fmt)
        if fail:
            cli.ExitCode.VERIFICATION_FAILED.exit()
        elif inconc:
            cli.ExitCode.VERIFICATION_INCONCLUSIVE.exit()
        cli.ExitCode.SUCCESS.exit()
    return wrapper


@app.command()
@handle_exceptions
@handle_outcomes
def ic3_invar(fname: cli.Path,
              bound: cli.Bound = 0,
              ltl: cli.Ltl = None,
              timeout: cli.Timeout = 0,
              format: cli.OutputFormat = cli.OutputFormat.PLAIN.value):
    """Verify invariant properties using IC3.

    This is a wrapper around `check_property_as_invar_ic3`.\n\n

    It only works for invariant properties, i.e., `G (predicate)`.
    """
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    bound, ltl, timeout = bound or None, ltl or [None], timeout or None
    return (
        '\n'.join(nuxmv.ic3_invar(bound, p, timeout) for p in ltl),
        format)


@app.command()
@handle_exceptions
@handle_outcomes
def ic3(fname: cli.Path,
        bound: cli.Bound = 0,
        ltl: cli.Ltl = None,
        timeout: cli.Timeout = 0,
        format: cli.OutputFormat = cli.OutputFormat.PLAIN.value):
    """Verify LTL properties using IC3.

    This is a wrapper around `check_ltlspec_ic3`.\n\n

    **BEWARE**: This implmementation of IC3 can only verify a (violated)
    property if it allows a finitely-representable (e.g., lasso-shaped) path as
    a counterexample. If that is not the case, it will **NOT** terminate!\n\n

    For safety properties, a workaround is to use `poetry ic3-invar` instead.
    """
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    bound, ltl, timeout = bound or None, ltl or [None], timeout or None
    return (
        '\n'.join(nuxmv.ic3(bound, p, timeout) for p in ltl),
        format)
