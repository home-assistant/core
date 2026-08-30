"""Coordinators for the iCloud integration."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, tzinfo
import logging
from typing import override

from pyicloud.exceptions import PyiCloudException
from pyicloud.services.calendar import CalendarService, EventObject
from pyicloud.services.reminders.client import RemindersApiError, RemindersAuthError
from pyicloud.services.reminders.service import RemindersService

from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .account import IcloudConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CALENDAR_SCAN_INTERVAL = timedelta(minutes=15)

# How much of the calendar to keep cached for the entity's current/next event.
# `async_get_events` queries iCloud directly for anything outside this window.
LOOKBACK = timedelta(days=1)
LOOKAHEAD = timedelta(days=30)


@dataclass(slots=True)
class IcloudCalendarData:
    """A calendar and the events cached for it."""

    name: str
    events: list[CalendarEvent]


def localize(value: date | datetime) -> datetime:
    """Return a comparable, timezone-aware datetime for a date or datetime."""
    if isinstance(value, datetime):
        return dt_util.as_local(value)
    return dt_util.start_of_local_day(value)


class IcloudCalendarCoordinator(DataUpdateCoordinator[dict[str, IcloudCalendarData]]):
    """Keep a rolling window of events cached for the current/next lookup."""

    def __init__(self, hass: HomeAssistant, entry: IcloudConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=CALENDAR_SCAN_INTERVAL,
        )
        self.account = entry.runtime_data

    @property
    def _calendars(self) -> CalendarService:
        """Return the calendar service of the authenticated account."""
        if (api := self.account.api) is None:
            raise ConfigEntryAuthFailed("iCloud account is not authenticated")
        return api.calendar

    def fetch_events(
        self, start: datetime, end: datetime, guids: list[str] | None = None
    ) -> dict[str, list[CalendarEvent]]:
        """Return events per calendar between two points. Runs in the executor."""
        service = self._calendars

        # An explicit empty list means no calendars, not every calendar.
        if guids is not None and not guids:
            return {}

        wanted = set(guids) if guids is not None else None
        result: dict[str, list[CalendarEvent]] = {guid: [] for guid in (wanted or ())}

        # pyicloud sends both bounds as plain dates, so iCloud answers with the
        # whole of each boundary day whatever times were asked for. Keep only
        # the events that really overlap the window.
        window_start = localize(start)
        window_end = localize(end)

        for event in service.get_events(from_dt=start, to_dt=end, as_objs=True):
            if wanted is not None and event.pguid not in wanted:
                continue
            if (parsed := _as_calendar_event(event)) is None:
                continue
            if (
                localize(parsed.start) >= window_end
                or localize(parsed.end) <= window_start
            ):
                continue
            result.setdefault(event.pguid, []).append(parsed)

        for events in result.values():
            events.sort(key=lambda event: localize(event.start))
        return result

    def _fetch(self) -> dict[str, IcloudCalendarData]:
        """Fetch the calendars and their events. Runs in the executor."""
        names = {
            calendar.guid: calendar.title
            for calendar in self._calendars.get_calendars(as_objs=True)
        }
        now = dt_util.now()
        events = self.fetch_events(now - LOOKBACK, now + LOOKAHEAD, list(names))

        return {
            guid: IcloudCalendarData(name=name, events=events.get(guid, []))
            for guid, name in names.items()
        }

    @override
    async def _async_update_data(self) -> dict[str, IcloudCalendarData]:
        """Fetch calendars and their upcoming events."""
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except PyiCloudException as err:
            raise UpdateFailed(f"Error fetching calendars: {err}") from err


def _parse_apple_date(value: datetime | list[int] | None) -> datetime | None:
    """Parse the date format iCloud returns for calendar events.

    ``EventObject`` is annotated as holding ``datetime``, but pyicloud hands
    back the wire format unchanged: ``[yyyymmdd, year, month, day, hour,
    minute, minutes_since_midnight]``. Both forms are accepted so this keeps
    working if that is ever changed upstream.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if len(value) >= 6:
        try:
            _, year, month, day, hour, minute = value[:6]
            return datetime(int(year), int(month), int(day), int(hour), int(minute))
        except TypeError, ValueError:
            _LOGGER.debug("Unparsable calendar date: %r", value)
    return None


def _event_timezone(event: EventObject) -> tzinfo:
    """Return the timezone an event's wall-clock times are expressed in.

    iCloud reports naive local times alongside a `tz` field. "Floating" means
    the event has no zone of its own and should follow the viewer, so fall
    back to Home Assistant's timezone in that case.
    """
    if (name := event.tz) and name != "Floating":
        try:
            if (zone := dt_util.get_time_zone(name)) is not None:
                return zone
        except ValueError:
            # get_time_zone rejects malformed keys rather than returning None.
            _LOGGER.debug("Unknown calendar event timezone: %r", name)
    return dt_util.get_default_time_zone()


def _as_calendar_event(event: EventObject) -> CalendarEvent | None:
    """Convert a pyicloud event into a Home Assistant calendar event."""
    start = _parse_apple_date(event.local_start_date) or _parse_apple_date(
        event.start_date
    )
    if start is None:
        return None

    end = _parse_apple_date(event.local_end_date) or _parse_apple_date(event.end_date)
    if end is None:
        end = start + timedelta(hours=1)

    start_value: date | datetime
    end_value: date | datetime
    if event.all_day:
        start_value = start.date()
        end_value = end.date()
        # Home Assistant treats the end of an all-day event as exclusive.
        if end_value <= start_value:
            end_value = start_value + timedelta(days=1)
    else:
        # The wire format is a naive wall-clock time; only a `datetime` from a
        # future pyicloud can already carry a zone, and replacing it would
        # move the event to a different instant.
        zone = _event_timezone(event)
        start_value = start if start.tzinfo else start.replace(tzinfo=zone)
        end_value = end if end.tzinfo else end.replace(tzinfo=zone)
        if end_value <= start_value:
            end_value = start_value + timedelta(minutes=30)

    return CalendarEvent(
        uid=event.guid or None,
        summary=event.title or "",
        start=start_value,
        end=end_value,
        location=event.location or None,
    )


REMINDERS_SCAN_INTERVAL = timedelta(minutes=5)

# pyicloud raises these for CloudKit failures; neither subclasses
# PyiCloudException, so both have to be caught explicitly.
# `get()` raises a bare LookupError when a reminder was removed elsewhere.
REMINDERS_ERRORS = (
    PyiCloudException,
    RemindersApiError,
    RemindersAuthError,
    LookupError,
)

# pyicloud substitutes this when a reminder's title cannot be decrypted, which
# happens on Advanced Data Protection accounts whose session has no Protected
# Cloud Storage key. `update()` rewrites TitleDocument and NotesDocument
# unconditionally, so writing such a reminder back would replace the real title
# with this placeholder and blank the notes.
UNDECODED_TITLE = "Error Decoding Title"

# Reminders are fetched one list at a time, so keep the per-list page bounded.
RESULTS_LIMIT = 200


@dataclass(slots=True)
class IcloudReminder:
    """A single reminder."""

    uid: str
    summary: str
    description: str | None
    due: date | datetime | None
    completed: bool
    completed_at: datetime | None
    parent_uid: str | None


@dataclass(slots=True)
class IcloudReminderList:
    """A reminder list and the reminders it holds."""

    list_id: str
    name: str
    reminders: list[IcloudReminder] = field(default_factory=list)


class IcloudRemindersCoordinator(DataUpdateCoordinator[dict[str, IcloudReminderList]]):
    """Fetch reminder lists and their contents."""

    def __init__(self, hass: HomeAssistant, entry: IcloudConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=REMINDERS_SCAN_INTERVAL,
        )
        self.account = entry.runtime_data
        self._warned_undecoded = False

    @property
    def reminders(self) -> RemindersService:
        """Return the reminders service of the authenticated account."""
        if (api := self.account.api) is None:
            raise ConfigEntryAuthFailed("iCloud account is not authenticated")
        return api.reminders

    def _fetch(self) -> dict[str, IcloudReminderList]:
        """Fetch every list and its reminders. Runs in the executor."""
        service = self.reminders
        result: dict[str, IcloudReminderList] = {}

        for list_id, name in _live_lists(service):
            batch = service.list_reminders(
                list_id=list_id,
                include_completed=True,
                results_limit=RESULTS_LIMIT,
            )
            result[list_id] = IcloudReminderList(
                list_id=list_id,
                name=name,
                reminders=[
                    _as_reminder(reminder)
                    for reminder in batch.reminders
                    if not reminder.deleted
                ],
            )

        return result

    @override
    async def _async_update_data(self) -> dict[str, IcloudReminderList]:
        """Fetch reminders from iCloud."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch)
        except REMINDERS_ERRORS as err:
            raise UpdateFailed(f"Error fetching reminders: {err}") from err

        self._warn_if_undecoded(data)
        return data

    def _warn_if_undecoded(self, data: dict[str, IcloudReminderList]) -> None:
        """Warn once if reminder titles came back encrypted.

        With Advanced Data Protection enabled, CloudKit only returns readable
        content to a session holding a Protected Cloud Storage key. Without it
        every title arrives as a placeholder, which is otherwise a confusing
        thing to see in a to-do list.
        """
        if self._warned_undecoded:
            return
        if not any(
            reminder.summary == UNDECODED_TITLE
            for reminder_list in data.values()
            for reminder in reminder_list.reminders
        ):
            return

        self._warned_undecoded = True
        _LOGGER.warning(
            "Some reminder titles could not be decrypted. This account uses "
            "Advanced Data Protection, so approve access on one of your Apple "
            "devices to make them readable"
        )


def _live_lists(service: RemindersService) -> list[tuple[str, str]]:
    """Return the ``(list_id, name)`` pairs that should become todo entities.

    ``lists()`` yields every List record in the CloudKit zone, which includes
    groups (a folder holding other lists) and the tombstones left behind by
    deleted lists. A group and a list inside it can share a name, so both must
    be skipped or the same name shows up twice, once permanently empty.

    ``deleted`` is read defensively: pyicloud exposes it on reminders but not
    yet on lists, so it is absent on current releases and the tombstones stay
    visible until it lands upstream.
    """
    return [
        (reminder_list.id, reminder_list.title)
        for reminder_list in service.lists()
        if not reminder_list.is_group and not getattr(reminder_list, "deleted", False)
    ]


def _as_reminder(reminder) -> IcloudReminder:
    """Convert a pyicloud reminder into the coordinator's model."""
    due = reminder.due_date
    if due is not None and reminder.all_day and isinstance(due, datetime):
        due = due.date()

    return IcloudReminder(
        uid=reminder.id,
        summary=reminder.title,
        description=reminder.desc or None,
        due=due,
        completed=reminder.completed,
        completed_at=reminder.completed_date,
        parent_uid=reminder.parent_reminder_id,
    )
