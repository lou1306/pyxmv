import importlib.metadata
from pathlib import Path
from sys import exit, stderr

import typer

from .cli import HeuristicsEnum, HeuristicsTyper, SeedTyper, StepsTyper
from .nuxmvint import NuXmvInt

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
def simulate(fname: Path,
             steps: StepsTyper = 0,
             seed: SeedTyper = None,
             heuristics: HeuristicsTyper = HeuristicsEnum.usr):
    """Simulate a nuxmv specification."""
    try:
        heur = heuristics.get(seed)
        nuxmv = NuXmvInt()
        nuxmv.msat_setup(fname)
        nuxmv.init(h=heur)
        steps = -1 if steps == 0 else steps
        while steps != 0:
            nuxmv.simulate(heuristic=heur)
            steps = steps - 1 if steps > 0 else -1
        else:
            print("Done")
            exit(0)
    except Exception as e:
        print(f"[ERROR] {e}", file=stderr)
        exit(1)
