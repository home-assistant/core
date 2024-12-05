"""Calendar platform for Habitica integration."""

from __future__ import annotations

from abc import abstractmethod
from datetime import date, datetime, timedelta
from enum import StrEnum

from dateutil.rrule import rrule

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
from .util import build_rrule, get_recurrence_rule


class HabiticaCalendar(StrEnum):
    """Habitica calendars."""

    DAILIES = "dailys"
    TODOS = "todos"
    TODO_REMINDERS = "todo_reminders"
    DAILY_REMINDERS = "daily_reminders"


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
            HabiticaTodoRemindersCalendarEntity(coordinator),
            HabiticaDailyRemindersCalendarEntity(coordinator),
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

    @abstractmethod
    def get_events(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> list[CalendarEvent]:
        """Return events."""

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""

        return next(iter(self.get_events(dt_util.now())), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        return self.get_events(start_date, end_date)

    @property
    def start_of_today(self) -> datetime:
        """Habitica daystart."""
        return dt_util.start_of_local_day(
            datetime.fromisoformat(self.coordinator.data.user["lastCron"])
        )

    def get_recurrence_dates(
        self, recurrences: rrule, start_date: datetime, end_date: datetime | None = None
    ) -> list[datetime]:
        """Calculate recurrence dates based on start_date and end_date."""
        if end_date:
            return recurrences.between(
                start_date, end_date - timedelta(days=1), inc=True
            )
        # if no end_date is given, return only the next recurrence
        return [recurrences.after(start_date, inc=True)]


class HabiticaTodosCalendarEntity(HabiticaCalendarEntity):
    """Habitica todos calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.TODOS,
        translation_key=HabiticaCalendar.TODOS,
    )

    def get_events(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> list[CalendarEvent]:
        """Get all dated todos."""

        events = []
        for task in self.coordinator.data.tasks:
            if not (
                task["type"] == HabiticaTaskType.TODO
                and not task["completed"]
                and task.get("date")  # only if has due date
            ):
                continue

            start = dt_util.start_of_local_day(datetime.fromisoformat(task["date"]))
            end = start + timedelta(days=1)
            # return current and upcoming events or events within the requested range

            if end < start_date:
                # Event ends before date range
                continue

            if end_date and start > end_date:
                # Event starts after date range
                continue

            events.append(
                CalendarEvent(
                    start=start.date(),
                    end=end.date(),
                    summary=task["text"],
                    description=task["notes"],
                    uid=task["id"],
                )
            )
        return sorted(
            events,
            key=lambda event: (
                event.start,
                self.coordinator.data.user["tasksOrder"]["todos"].index(event.uid),
            ),
        )


class HabiticaDailiesCalendarEntity(HabiticaCalendarEntity):
    """Habitica dailies calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.DAILIES,
        translation_key=HabiticaCalendar.DAILIES,
    )

    def end_date(self, recurrence: datetime, end: datetime | None = None) -> date:
        """Calculate the end date for a yesterdaily.

        The enddates of events from yesterday move forward to the end
        of the current day (until the cron resets the dailies) to show them
        as still active events on the calendar state entity (state: on).

        Events in the calendar view will show all-day events on their due day
        """
        if end:
            return recurrence.date() + timedelta(days=1)
        return (
            dt_util.start_of_local_day()
            if recurrence == self.start_of_today
            else recurrence
        ).date() + timedelta(days=1)

    def get_events(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> list[CalendarEvent]:
        """Get dailies and recurrences for a given period or the next upcoming."""

        # we only have dailies for today and future recurrences
        if end_date and end_date < self.start_of_today:
            return []
        start_date = max(start_date, self.start_of_today)

        events = []
        for task in self.coordinator.data.tasks:
            #  only dailies that that are not 'grey dailies'
            if not (task["type"] == HabiticaTaskType.DAILY and task["everyX"]):
                continue

            recurrences = build_rrule(task)
            recurrence_dates = self.get_recurrence_dates(
                recurrences, start_date, end_date
            )
            for recurrence in recurrence_dates:
                is_future_event = recurrence > self.start_of_today
                is_current_event = (
                    recurrence <= self.start_of_today and not task["completed"]
                )

                if not is_future_event and not is_current_event:
                    continue

                events.append(
                    CalendarEvent(
                        start=recurrence.date(),
                        end=self.end_date(recurrence, end_date),
                        summary=task["text"],
                        description=task["notes"],
                        uid=task["id"],
                        rrule=get_recurrence_rule(recurrences),
                    )
                )
        return sorted(
            events,
            key=lambda event: (
                event.start,
                self.coordinator.data.user["tasksOrder"]["dailys"].index(event.uid),
            ),
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return next(iter(self.get_events(self.start_of_today)), None)

    @property
    def extra_state_attributes(self) -> dict[str, bool | None] | None:
        """Return entity specific state attributes."""
        return {
            "yesterdaily": self.event.start < self.start_of_today.date()
            if self.event
            else None
        }


class HabiticaTodoRemindersCalendarEntity(HabiticaCalendarEntity):
    """Habitica to-do reminders calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.TODO_REMINDERS,
        translation_key=HabiticaCalendar.TODO_REMINDERS,
    )

    def get_events(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> list[CalendarEvent]:
        """Reminders for todos."""

        events = []

        for task in self.coordinator.data.tasks:
            if task["type"] != HabiticaTaskType.TODO or task["completed"]:
                continue

            for reminder in task.get("reminders", []):
                # reminders are returned by the API in local time but with wrong
                # timezone (UTC) and arbitrary added seconds/microseconds. When
                # creating reminders in Habitica only hours and minutes can be defined.
                start = datetime.fromisoformat(reminder["time"]).replace(
                    tzinfo=dt_util.DEFAULT_TIME_ZONE, second=0, microsecond=0
                )
                end = start + timedelta(hours=1)

                if end < start_date:
                    # Event ends before date range
                    continue

                if end_date and start > end_date:
                    # Event starts after date range
                    continue

                events.append(
                    CalendarEvent(
                        start=start,
                        end=end,
                        summary=task["text"],
                        description=task["notes"],
                        uid=f"{task["id"]}_{reminder["id"]}",
                    )
                )

        return sorted(
            events,
            key=lambda event: event.start,
        )


class HabiticaDailyRemindersCalendarEntity(HabiticaCalendarEntity):
    """Habitica daily reminders calendar entity."""

    entity_description = CalendarEntityDescription(
        key=HabiticaCalendar.DAILY_REMINDERS,
        translation_key=HabiticaCalendar.DAILY_REMINDERS,
    )

    def start(self, reminder_time: str, reminder_date: date) -> datetime:
        """Generate reminder times for dailies.

        Reminders for dailies have a datetime but the date part is arbitrary,
        only the time part is evaluated. The dates for the reminders are the
        dailies' due dates.
        """
        return datetime.combine(
            reminder_date,
            datetime.fromisoformat(reminder_time)
            .replace(
                second=0,
                microsecond=0,
            )
            .time(),
            tzinfo=dt_util.DEFAULT_TIME_ZONE,
        )

    def get_events(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> list[CalendarEvent]:
        """Reminders for dailies."""

        events = []
        if end_date and end_date < self.start_of_today:
            return []
        start_date = max(start_date, self.start_of_today)

        for task in self.coordinator.data.tasks:
            if not (task["type"] == HabiticaTaskType.DAILY and task["everyX"]):
                continue

            recurrences = build_rrule(task)
            recurrences_start = self.start_of_today

            recurrence_dates = self.get_recurrence_dates(
                recurrences, recurrences_start, end_date
            )
            for recurrence in recurrence_dates:
                is_future_event = recurrence > self.start_of_today
                is_current_event = (
                    recurrence <= self.start_of_today and not task["completed"]
                )

                if not is_future_event and not is_current_event:
                    continue

                for reminder in task.get("reminders", []):
                    start = self.start(reminder["time"], recurrence)
                    end = start + timedelta(hours=1)

                    if end < start_date:
                        # Event ends before date range
                        continue

                    events.append(
                        CalendarEvent(
                            start=start,
                            end=end,
                            summary=task["text"],
                            description=task["notes"],
                            uid=f"{task["id"]}_{reminder["id"]}",
                        )
                    )

        return sorted(
            events,
            key=lambda event: event.start,
        )
