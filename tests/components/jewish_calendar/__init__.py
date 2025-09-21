"""Tests for the jewish_calendar component."""

from dataclasses import dataclass
import datetime as dt


@dataclass(frozen=True)
class TestCase:
    """Single test case."""

    time: dt.datetime
    expected: str | int | bool | list | dict | None


@dataclass(frozen=True)
class TestSequence:
    """Sequence of test cases."""

    cases: list[TestCase]
