"""Local storage for the Local To-do integration."""

import asyncio
from collections.abc import Mapping
from pathlib import Path

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.os_error import os_write_error


def _repair_legacy_crlf_newlines(content: str) -> str:
    r"""Repair ICS content corrupted by CRLF newlines from ical <= 12.1.3.

    In ical <= 12.1.3, TextEncoder escaped \n to \\n but left \r unescaped.
    When read with Python's universal newlines mode (newline=None), any lone \r
    before \\n was converted into \n\\n, breaking property line parsing.
    """
    return content.replace("\r\\n", "\\n").replace("\n\\n", "\\n").replace("\r", "")


def parse_calendar(ics: str) -> tuple[Calendar, bool]:
    """Parse a calendar, and tell whether malformed newlines had to be repaired."""
    try:
        return IcsCalendarStream.calendar_from_ics(ics), False
    except CalendarParseError:
        repaired_ics = _repair_legacy_crlf_newlines(ics)
        if repaired_ics == ics:
            raise
        return IcsCalendarStream.calendar_from_ics(repaired_ics), True


def change_sections(calendar: Calendar, changes: Mapping[str, str | None]) -> bool:
    """Rename sections of the items, or clear them when mapped to None."""
    changed = False
    for todo in calendar.todos:
        if todo.categories and todo.categories[0] in changes:
            new_section = changes[todo.categories[0]]
            todo.categories = [new_section] if new_section else []
            changed = True
    return changed


class LocalTodoListStore:
    """Local storage for a single To-do list."""

    def __init__(self, hass: HomeAssistant, path: Path) -> None:
        """Initialize LocalTodoListStore."""
        self._hass = hass
        self._path = path
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        """Return the path of the calendar file."""
        return self._path

    async def async_load(self) -> str:
        """Load the calendar from disk."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._load)

    def _load(self) -> str:
        """Load the calendar from disk."""
        if not self._path.exists():
            return ""
        return self._path.read_text(encoding="utf-8")

    async def async_store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        async with self._lock:
            try:
                await self._hass.async_add_executor_job(self._store, ics_content)
            except OSError as err:
                raise os_write_error(err, str(self._path)) from err

    def _store(self, ics_content: str) -> None:
        """Persist the calendar to storage."""
        self._path.write_text(ics_content, encoding="utf-8")

    async def async_change_sections(self, changes: Mapping[str, str | None]) -> None:
        """Rename sections of the items, or clear them when mapped to None."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._change_sections, changes)

    def _change_sections(self, changes: Mapping[str, str | None]) -> None:
        """Rename sections of the items, or clear them when mapped to None."""
        if not (ics := self._load()):
            return
        calendar, _ = parse_calendar(ics)
        if change_sections(calendar, changes):
            try:
                self._store(IcsCalendarStream.calendar_to_ics(calendar))
            except OSError as err:
                raise os_write_error(err, str(self._path)) from err
