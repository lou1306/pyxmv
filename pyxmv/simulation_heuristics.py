from abc import ABC, abstractmethod
from enum import Enum
from random import Random
import time
from typing import Sequence


class HeuristicsEnum(str, Enum):
    usr = "user"
    rnd = "random"

    def get(self, seed: int | float | None):
        return {
            HeuristicsEnum.usr: UserChoice(),
            HeuristicsEnum.rnd: RandomChoice(seed)
        }[self]


class SimulationHeuristic(ABC):
    @abstractmethod
    def choose_from(self, states: Sequence) -> int:
        raise NotImplementedError()


class RandomChoice(SimulationHeuristic):
    def __init__(self, seed: int | float | None = None) -> None:
        self.rng = Random(time.time() if seed is None else seed)

    def choose_from(self, states: Sequence) -> int:
        return self.rng.randrange(len(states))


class UserChoice(SimulationHeuristic):
    def __init__(self) -> None:
        self.states = []

    def choose_from(self, states: Sequence) -> int:
        bound = len(states)
        if bound == 0:
            return 0
        choice = -1
        while not 0 <= choice < bound:
            try:
                choice = int(input(f"Choose a state (0-{bound - 1}): "))
            except ValueError:
                choice = -1
                continue
        return choice
