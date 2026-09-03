"""Tests for the jewish_calendar component."""

from dataclasses import dataclass
import datetime as dt
from typing import Protocol

from homeassistant.core import HomeAssistant


class GetCalendarEvents(Protocol):
    """Return the events of a calendar entity within a date range."""

    async def __call__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        start_date: dt.datetime,
        end_date: dt.datetime | None = None,
    ) -> list[dict[str, str]]: ...


@dataclass(frozen=True)
class TimeValue:
    """Single test case."""

    time: dt.datetime
    expected: str | int | bool | list | dict | None


@dataclass(frozen=True)
class TimeValueSequence:
    """Sequence of test cases."""

    cases: list[TimeValue]
