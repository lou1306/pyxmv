import importlib.metadata
from functools import wraps
from sys import exit

import typer

from .cli import (ErrorCode, HeuristicsEnum, HeuristicsTyper, PathTyper,
                  SeedTyper, StepsTyper, TimeoutTyper)
from .nuxmvint import NuXmvInt, PyXmvTimeout
from .outcome import Outcome, Verdict

app = typer.Typer()


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
def simulate(fname: PathTyper,
             steps: StepsTyper = 0,
             seed: SeedTyper = None,
             heuristics: HeuristicsTyper = HeuristicsEnum.usr):
    """Simulates a nuxmv model."""
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
        exit(ErrorCode.SUCCESS.value)


def handle_timeout(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except PyXmvTimeout:
            print("Timeout")
            ErrorCode.TIMEOUT.exit()
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
            ErrorCode.VERIFICATION_FAILED.exit()
        elif inconc:
            ErrorCode.VERIFICATION_INCONCLUSIVE.exit()
        ErrorCode.SUCCESS.exit()
    return wrapper


@app.command()
@handle_timeout
@handle_outcomes
def ic3_invar(fname: PathTyper, timeout: TimeoutTyper = 0):
    """Verifies invariant properties using IC3."""
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    return nuxmv.ic3_invar(timeout=timeout or None)


@app.command()
@handle_timeout
@handle_outcomes
def ic3(fname: PathTyper, timeout: TimeoutTyper = 0):
    """Verifies LTL properties using IC3."""
    nuxmv = NuXmvInt()
    nuxmv.msat_setup(fname)
    return nuxmv.ic3(timeout=timeout or None)
