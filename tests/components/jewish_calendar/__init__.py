"""Tests for the jewish_calendar component."""

from dataclasses import dataclass
import datetime as dt


@dataclass(frozen=True)
class TimeValue:
    """Single test case."""

    time: dt.datetime
    expected: str | int | bool | list | dict | None


@dataclass(frozen=True)
class TimeValueSequence:
    """Sequence of test cases."""

    cases: list[TimeValue]
