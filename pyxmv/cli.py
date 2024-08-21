from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from .simulation_heuristics import HeuristicsEnum


PathTyper = Annotated[
    Path,
    typer.Argument(help="Path to a nuXmv model.")
]

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
    typer.Option(help="Simulation bound (set to 0 for no bound).", min=0)]

TimeoutTyper = Annotated[
    int,
    typer.Option(help="Time limit (set to 0 for no limit).", min=0)]


class ErrorCode(Enum):
    """
    Exit codes for the pyXmv command-line utility.

    We strive to follow the conventions laid out in CPROVER, see e.g.:
    https://github.com/diffblue/cbmc/blob/b21323f5bbf60c98492f9166a047fa01fee4d179/src/util/exit_codes.h

    Only exceptions are codes 1 and 2 which are already taken by Typer/Click,
    respectively for uncaught exceptions and CLI usage mistakes.
    """

    SUCCESS = 0
    """Pretty self-explanatory."""
    TYPER_EXCEPTION = 1
    """Typer uses error code 1 for all uncaught expressions"""
    TYPER_USAGE = 2
    """Typer uses error code 2 for usage errors"""
    VERIFICATION_INCONCLUSIVE = 5
    """A verification task gives unknown as verdict"""
    INTERNAL_ERROR = 6
    """Errors on the backend side (e.g., parsing failed)"""
    VERIFICATION_FAILED = 10
    """A verification task gives false as verdict"""
    TIMEOUT = 124
    """An operation timed out"""


    def exit(self):
        exit(self.value)
