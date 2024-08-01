from enum import Enum
from typing import Annotated

import typer

from .simulation_heuristics import HeuristicsEnum


HeuristicsTyper = Annotated[
    HeuristicsEnum,
    typer.Option(help="How successor states are chosen.")]

SeedTyper = Annotated[
    int,
    typer.Option(
        help="Seed for the PRNG (if not set, system time will be used).",
        min=0)]

StepsTyper = Annotated[
    int,
    typer.Option(
        help="Simulation bound (set to 0 for no bound).",
        min=0)]
