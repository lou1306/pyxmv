from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from itertools import pairwise
from typing import Iterable

from .utils import fifo_cache


class Verdict(Enum):
    TRUE = "SUCCESSFUL"
    FALSE = "FAILED"
    UNKNOWN = "INCONCLUSIVE"


Value = str | int | float | bool
StrState = dict[str, str]
"""String-valued state"""
ParsedState = dict[str, Value]
State = ParsedState | StrState

LOOP_STARTS_HERE = "-- Loop starts here"


@dataclass
class Trace:
    trace_description: str
    trace_type: str
    states: Sequence[StrState]
    loop_indexes: Collection[int]

    @staticmethod
    @fifo_cache()
    def parse_state(text: str) -> tuple[StrState, bool]:
        """Parse nuxmv output into a dictionary.

        Args:
            text (str): unparsed state from nuXmv

        Returns:
            result (tuple): A tuple containing

            - the parsed state
            - `True` if the _next_ state will be the start of a loop,
              `False` otherwise
        """
        lines = text.splitlines()
        state = {}
        loop_starts_next = False
        for line in lines:
            line = line.strip()
            loop_starts_next |= line.startswith(LOOP_STARTS_HERE)
            if line and not line.startswith("--"):
                lhs, rhs = line.split("=")
                state[lhs.strip()] = rhs.strip()
        return state, loop_starts_next

    @staticmethod
    def parse_list_of_str(states: Sequence[str]) -> tuple[Sequence[StrState], Collection[int]]:  # noqa: E501
        """Parse a sequence of strings into states and loop indices."""
        str_states, loop_starts = zip(*(Trace.parse_state(s) for s in states))
        return str_states, frozenset([i+1 for i, x in enumerate(loop_starts) if x])  # noqa: E501

    @staticmethod
    def of_states(states: Sequence[str], type_: str, descr: str) -> "Trace":
        """Turn a sequence of strings into a Trace."""
        str_states, loop_starts = Trace.parse_list_of_str(states)
        return Trace(descr, type_, str_states, loop_starts)

    @staticmethod
    def parse(text: str) -> "Trace":
        """Parse nuXmv output into a Trace"""
        start = text.find("\nTrace Description:")
        body = text[start+1:]
        descr_type, *states = body.split("->")
        loop_starts_at_0 = LOOP_STARTS_HERE in descr_type
        states = [s.split("<-")[1] for s in states]
        str_states, loop_starts = Trace.parse_list_of_str(states)
        if loop_starts_at_0:
            loop_starts = frozenset({0, *loop_starts})
        descr, trace_type = descr_type.splitlines()[:2]
        descr = descr.split("Trace Description:")[1].strip()
        trace_type = trace_type.split("Type:")[1].strip()
        return Trace(descr, trace_type, str_states, loop_starts)

    def parsed_states(self, full: bool = False) -> Iterable[ParsedState]:
        @fifo_cache(64)
        def try_parse(value: str) -> Value:
            if value in ("TRUE", "FALSE"):
                return bool(value == "TRUE")
            try:
                parsed = float(value)
                return int(parsed) if parsed.is_integer() else parsed
            except ValueError:
                return value

        for s in (self.full_states() if full else self.states):
            yield {k: try_parse(v) for k, v in s.items()}

    def get_states(self, full: bool, parse: bool) -> Iterable[State]:
        if parse:
            yield from self.parsed_states(full)
        elif full:
            yield from self.full_states()
        else:
            yield from self.states

    def full_states(self) -> Iterable[StrState]:
        accum: StrState = {}
        for state in self.states:
            accum |= state
            yield accum

    def as_dict(self, *, full: bool = False, parse: bool = False) -> dict:
        def factory(kv_pairs):
            result = {k: v for k, v in kv_pairs if k != "states"}
            result["states"] = list(self.get_states(full, parse))
            return result
        return asdict(self, dict_factory=factory)

    def pprint(self, *, full: bool = False) -> Iterable[str]:
        yield f"""Trace Description: {self.trace_description or "N/A"}"""
        yield f"""Trace Type: {self.trace_type or "N/A"}"""
        if self.states:
            for i, state in enumerate(self.get_states(full, False)):
                if i in self.loop_indexes:
                    yield "  " + LOOP_STARTS_HERE
                yield f"  -> State: 1.{i+1} <-"
                for k, v in state.items():
                    yield f"    {k} = {v}"


@dataclass
class Outcome:
    logic: str
    specification: str
    verdict: Verdict
    trace: Trace | None
    unparsed: str

    @staticmethod
    def parse(text: str) -> Iterable["Outcome"]:
        places = []
        outcome_strings = ("is true", "is false", "is unknown")
        for search in outcome_strings:
            x = text.find(search)
            while x != -1:
                places.append(x)
                x = text.find(search, x+1)
        places = [text.rfind("--", 0, place) for place in sorted(places)]

        for start, end in pairwise([*places, len(text)]):
            text_slice = text[start:end]
            verdict = (
                Verdict.TRUE if "is true" in text_slice
                else Verdict.UNKNOWN if "is unknown" in text_slice
                else Verdict.FALSE)
            header_end = text_slice.find("\n")
            header = text_slice[:header_end].strip()
            logic = header[3:header.find(" ", 3)].strip()
            spec = header.split("specification")[1]
            for s in outcome_strings:
                spec = spec.replace(s, "")
            spec = spec.strip()
            trace = Trace.parse(text_slice) if verdict == Verdict.FALSE else None  # noqa: E501
            yield Outcome(logic, spec, verdict, trace, text_slice)

    def pprint(self) -> Iterable[str]:
        yield (
            f"VERIFICATION {self.verdict.value} "
            f"for {self.specification} "
            f"({self.logic})")
        if self.trace is not None:
            yield from self.trace.pprint()

    def as_dict(self, *, full: bool = False, parse: bool = False) -> dict:
        def factory(kv_pairs):
            result = {k: v for k, v in kv_pairs if k != "trace"}
            result["trace"] = self.trace.as_dict(full=full, parse=parse)
            return result
        return asdict(self, dict_factory=factory)
