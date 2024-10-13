"""Calendar platform for Habitica integration."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from enum import StrEnum

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HabiticaConfigEntry
from .coordinator import HabiticaDataUpdateCoordinator
from .entity import HabiticaBase
from .types import HabiticaTaskType
from .util import build_rrule, to_date


class HabiticaCalendar(StrEnum):
    """Habitica calendars."""

    DAILIES = "dailys"
    TODOS = "todos"
    REMINDERS = "reminders"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HabiticaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        [
            HabiticaTodosCalendarEntity(coordinator),
            HabiticaDailiesCalendarEntity(coordinator),
            HabiticaRemindersCalendarEntity(coordinator),
        ]
    )


class HabiticaCalendarEntity(HabiticaBase, CalendarEntity):
    """Base Habitica calendar entity."""

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
    ) -> None:
        """Initialize calendar entity."""
        super().__init__(coordinator, self.entity_description)


class HabiticaTodosCalendarEntity(HabiticaCalendarEntity):
    """Habitica todos calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.TODOS,
        translation_key=HabiticaCalendar.TODOS,
    )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""

        events = [
            CalendarEvent(
                start=start,
                end=start + timedelta(days=1),
                summary=task["text"],
                description=task["notes"],
                uid=task["id"],
            )
            for task in self.coordinator.data.tasks
            if task["type"] == HabiticaTaskType.TODO
            and not task["completed"]
            and task.get("date")
            and (start := to_date(task["date"]))
            and start >= dt_util.now().date()
        ]
        events_sorted = sorted(
            events,
            key=lambda event: (
                event.start,
                self.coordinator.data.user["tasksOrder"]["todos"].index(event.uid),
            ),
        )

        return events_sorted[0] if events_sorted else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        return [
            CalendarEvent(
                start=start,
                end=start + timedelta(days=1),
                summary=task["text"],
                description=task["notes"],
                uid=task["id"],
            )
            for task in self.coordinator.data.tasks
            if task["type"] == HabiticaTaskType.TODO
            and not task["completed"]
            and task.get("date")
            and (start := to_date(task["date"]))
            and (start_date.date() <= start <= end_date.date())
        ]


class HabiticaDailiesCalendarEntity(HabiticaCalendarEntity):
    """Habitica dailies calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.DAILIES,
        translation_key=HabiticaCalendar.DAILIES,
    )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""

        today = datetime.combine(
            dt_util.now().date(), time(), dt_util.DEFAULT_TIME_ZONE
        )
        events = [
            CalendarEvent(
                start=(start := next_recurrence.date()),
                end=start + timedelta(days=1),
                summary=task["text"],
                description=task["notes"],
                uid=task["id"],
            )
            for task in self.coordinator.data.tasks
            if task["type"] == HabiticaTaskType.DAILY
            and not task["completed"]
            and task["everyX"]
            if (next_recurrence := build_rrule(task).after(today, inc=True))
        ]
        events_sorted = sorted(
            events,
            key=lambda event: (
                event.start,
                self.coordinator.data.user["tasksOrder"]["dailys"].index(event.uid),
            ),
        )

        return events_sorted[0] if events_sorted else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        today = to_date(self.coordinator.data.user["lastCron"])
        # returns only todays and future dailies.
        # If a daily is completed it will not be shown for today but still future recurrences
        # If the cron hasn't run, not completed dailies are yesterdailies and displayed yesterday
        return [
            CalendarEvent(
                start=start,
                end=start + timedelta(days=1),
                summary=task["text"],
                description=task["notes"],
                uid=task["id"],
                rrule=str(build_rrule(task))[30:],
            )
            for task in self.coordinator.data.tasks
            if task["type"] == HabiticaTaskType.DAILY and task["everyX"]
            for recurrence in build_rrule(task).between(start_date, end_date, inc=True)
            if (start := recurrence.date()) > today
            or (start == today and not task["completed"])
        ]


class HabiticaRemindersCalendarEntity(HabiticaCalendarEntity):
    """Habitica reminders calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.REMINDERS,
        translation_key=HabiticaCalendar.REMINDERS,
    )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        events = [
            CalendarEvent(
                start=start,
                end=start + timedelta(hours=1),
                summary=task["text"],
                description=task["notes"],
                uid=f"{task["id"]}_{reminder["id"]}",
            )
            for task in self.coordinator.data.tasks
            if task["type"] in (HabiticaTaskType.DAILY, HabiticaTaskType.TODO)
            and not task["completed"]
            for reminder in task.get("reminders", [])
            if (
                start := datetime.fromisoformat(reminder["time"]).replace(
                    tzinfo=dt_util.DEFAULT_TIME_ZONE
                )
            )
            >= (now - timedelta(hours=1))
        ]

        events_sorted = sorted(
            events,
            key=lambda event: event.start,
        )

        # return the last reminder that went off in the last hour
        if past_events := [
            event
            for event in events_sorted
            if now >= event.start >= (now - timedelta(hours=1))
        ]:
            return past_events[-1]

        # if there is no active reminder, move on to the next upcoming event
        if upcoming_events := [event for event in events_sorted if event.start > now]:
            return upcoming_events[0]
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        return [
            CalendarEvent(
                start=start,
                end=start + timedelta(hours=1),
                summary=task["text"],
                description=task["notes"],
                uid=f"{task["id"]}_{reminder["id"]}",
            )
            for task in self.coordinator.data.tasks
            if task["type"] in (HabiticaTaskType.DAILY, HabiticaTaskType.TODO)
            and not task["completed"]
            for reminder in task.get("reminders", [])
            if (
                start_date
                <= (
                    start := datetime.fromisoformat(reminder["time"]).replace(
                        tzinfo=dt_util.DEFAULT_TIME_ZONE
                    )
                )
                <= end_date
            )
        ]
