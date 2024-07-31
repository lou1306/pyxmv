from enum import Enum
from pathlib import Path
from sys import exit, stderr

from pyxmv.simulation_heuristics import RandomChoice, UserChoice
import typer

from .nuxmvint import NuXmvInt


app = typer.Typer()


class HeuristicsEnum(str, Enum):
    usr = "user"
    rnd = "random"

    def getClass(self):
        return {
            HeuristicsEnum.usr: UserChoice,
            HeuristicsEnum.rnd: RandomChoice
        }[self]


@app.command()
def simulate(fname: Path,
             steps: int = -1,
             heuristics: HeuristicsEnum = HeuristicsEnum.usr):
    try:
        heur = heuristics.getClass()
        nuxmv = NuXmvInt()
        nuxmv.msat_setup(str(fname))
        nuxmv.init()
        while steps != 0:
            nuxmv.simulate(heuristic=heur())
            steps = steps - 1 if steps > 0 else -1
        else:
            print("Done")
            exit(0)
    except Exception as e:
        print(f"[ERROR] {e}", file=stderr)
        exit(1)
