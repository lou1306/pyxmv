from dataclasses import dataclass
from collections.abc import Collection, Sequence
from enum import StrEnum
from itertools import pairwise
from typing import Iterable, Optional


class Verdict(StrEnum):
    TRUE = "SUCCESSFUL"
    FALSE = "FAILED"
    UNKNOWN = "INCONCLUSIVE"


@dataclass
class Trace:
    trace_description: str
    trace_type: str
    states: Sequence[dict[str, str]]
    loop_indexes: Collection[int]

    @staticmethod
    def parse_state(text: str) -> tuple[dict[str, str], bool]:
        lines = text.splitlines()
        state = {}
        loop_starts_next = False
        for line in lines:
            line = line.strip()
            loop_starts_next = line.startswith("-- Loop starts here")
            if line and not line.startswith("--"):
                lhs, rhs = line.split("=")
                state[lhs.strip()] = rhs.strip()
        return state, loop_starts_next

    @staticmethod
    def parse(text: str) -> Optional["Trace"]:
        if "is true" in text or "is unknown" in text:
            return None
        start = text.find("\nTrace Description:")
        body = text[start+1:]
        descr_type, *states = body.split("->")
        states = [s.split("<-")[1] for s in states]
        states, loop_starts = zip(*(Trace.parse_state(s) for s in states))
        loop_starts = frozenset([i for i, x in enumerate(loop_starts) if x])
        descr, trace_type = descr_type.splitlines()[:2]
        descr = descr.split("Trace Description:")[1].strip()
        trace_type = trace_type.split("Type:")[1].strip()
        return Trace(descr, trace_type, states, loop_starts)

    def parsed_states(self, full: bool = False) -> Iterable[dict[str, str | int | float]]:  # noqa: E501
        def try_parse(value: str) -> str | int | float:
            if value in ("TRUE", "FALSE"):
                return bool(value == "TRUE")
            try:
                parsed = float(value)
                return int(parsed) if parsed.is_integer else parsed
            except ValueError:
                return value

        for s in (self.full_states() if full else self.states):
            yield {k: try_parse(v) for k, v in s.items()}

    def get_states(self, full, parse):
        if parse:
            yield from self.parsed_states(full)
        yield from (self.full_states() if full else self.states)

    def full_states(self) -> Iterable[dict[str, str]]:
        accum = {}
        for state in self.states:
            accum |= state
            yield accum

    def pprint(self, *, full: bool = False, parse: bool = False) -> str:
        result = [
            f"Type: {self.trace_type}" if self.trace_type else "",
            f"Description: {self.trace_description}" if self.trace_description else ""]  # noqa: E501
        if self.states:
            for state in self.get_states(full, parse):
                result.append(str(state))
        return "\n".join(result)


@dataclass
class Outcome:
    logic: str
    specification: str
    verdict: Verdict
    trace: Optional[Trace]
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
            trace = Trace.parse(text_slice)
            yield Outcome(logic, spec, verdict, trace, text_slice)

    def message(self) -> str:
        return (
            f"VERIFICATION {self.verdict.value} "
            f"for {self.specification} "
            f"({self.logic})")
