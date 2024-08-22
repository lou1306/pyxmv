import importlib.metadata
from functools import wraps
from sys import exit

import typer

from . import cli
from .nuxmvint import NuXmvInt, PyXmvError, PyXmvTimeout
from .outcome import Outcome, Verdict

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


@app.command()
def simulate(fname: cli.Path,
             steps: cli.Steps = 0,
             seed: cli.Seed = None,
             heuristics: cli.Heuristics = cli.HeuristicsEnum.usr):
    """Simulate a nuxmv model."""
    heur = heuristics.get(seed)
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    nuxmv.init(h=heur)
    steps = steps or -1
    while steps != 0:
        nuxmv.simulate(heuristic=heur)
        steps = steps - 1 if steps > 0 else -1
    else:
        print("Done")
        cli.ErrorCode.SUCCESS.exit()


def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PyXmvTimeout:
            cli.ErrorCode.TIMEOUT.exit("Timeout")
        except PyXmvError as err:
            if DEBUG:
                raise err
            cli.ErrorCode.INTERNAL_ERROR.exit(str(err))
    return wrapper


def handle_outcomes(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cex = func(*args, **kwargs)
        fail = False
        inconc = False
        for outcome in Outcome.parse(cex):
            print(outcome.message())
            inconc |= outcome.verdict == Verdict.UNKNOWN
            if outcome.verdict == Verdict.FALSE:
                fail = True
                print(outcome.trace.pprint())
        if fail:
            cli.ErrorCode.VERIFICATION_FAILED.exit()
        elif inconc:
            cli.ErrorCode.VERIFICATION_INCONCLUSIVE.exit()
        cli.ErrorCode.SUCCESS.exit()
    return wrapper


@app.command()
@handle_exceptions
@handle_outcomes
def ic3_invar(fname: cli.Path, timeout: cli.Timeout = 0, ltl: cli.Ltl = None):
    """Verify invariant properties using IC3.

    This is a wrapper around `check_property_as_invar_ic3`.\n\n

    It only works for invariant properties, i.e., `G (predicate)`.
    """
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    ltl = ltl or [None]
    return '\n'.join(
        nuxmv.ic3_invar(ltlspec=p, timeout=timeout or None) for p in ltl)


@app.command()
@handle_exceptions
@handle_outcomes
def ic3(fname: cli.Path, timeout: cli.Timeout = 0, ltl: cli.Ltl = None):
    """Verify LTL properties using IC3.

    This is a wrapper around `check_ltlspec_ic3`.\n\n

    **BEWARE**: This implmementation of IC3 can only verify a (violated)
    property if it allows a finitely-representable (e.g., lasso-shaped) path as
    a counterexample. If that is not the case, it will **NOT** terminate!\n\n

    For safety properties, a workaround is to use `poetry ic3-invar` instead.
    """
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    ltl = ltl or [None]
    return '\n'.join(
        nuxmv.ic3(ltlspec=p, timeout=timeout or None) for p in ltl)
