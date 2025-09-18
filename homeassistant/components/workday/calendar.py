"""Workday Calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from holidays import HolidayBase

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WorkdayConfigEntry
from .const import CONF_EXCLUDES, CONF_OFFSET, CONF_WORKDAYS
from .entity import BaseWorkdayEntity

CALENDAR_DAYS_AHEAD = 365


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WorkdayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Holiday Calendar config entry."""
    days_offset: int = int(entry.options[CONF_OFFSET])
    excludes: list[str] = entry.options[CONF_EXCLUDES]
    sensor_name: str = entry.options[CONF_NAME]
    workdays: list[str] = entry.options[CONF_WORKDAYS]
    obj_holidays = entry.runtime_data

    async_add_entities(
        [
            WorkdayCalendarEntity(
                obj_holidays,
                workdays,
                excludes,
                days_offset,
                sensor_name,
                entry.entry_id,
            )
        ],
    )


class WorkdayCalendarEntity(BaseWorkdayEntity, CalendarEntity):
    """Representation of a Workday Calendar."""

    def __init__(
        self,
        obj_holidays: HolidayBase,
        workdays: list[str],
        excludes: list[str],
        days_offset: int,
        name: str,
        entry_id: str,
    ) -> None:
        """Initialize WorkdayCalendarEntity."""
        super().__init__(
            obj_holidays,
            workdays,
            excludes,
            days_offset,
            name,
            entry_id,
        )
        self._attr_unique_id = entry_id
        self._attr_event = None
        self.event_list: list[CalendarEvent] = []
        self._name = name

    def update_data(self, now: datetime) -> None:
        """Update data."""
        event_list = []
        for i in range(CALENDAR_DAYS_AHEAD):
            future_date = now.date() + timedelta(days=i)
            if self.date_is_workday(future_date):
                event = CalendarEvent(
                    summary=self._name,
                    start=future_date,
                    end=future_date,
                )
                event_list.append(event)
        self.event_list = event_list

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return (
            sorted(self.event_list, key=lambda e: e.start)[0]
            if self.event_list
            else None
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return [
            workday
            for workday in self.event_list
            if start_date.date() <= workday.start <= end_date.date()
        ]
