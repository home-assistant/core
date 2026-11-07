"""Support for WebDav Calendar."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from functools import partial
import logging
from typing import Any, cast, override

from caldav.calendarobjectresource import Event
from caldav.davclient import DAVClient
from caldav.lib.error import (
    DAVError,
    ETagMismatchError,
    NotFoundError,
    ScheduleTagMismatchError,
)
from caldav.lib.http_sync import requests as caldav_requests
from dateutil.rrule import rrulebase, rrulestr
import icalendar
import probatio

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_LOCATION,
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    PLATFORM_SCHEMA as CALENDAR_PLATFORM_SCHEMA,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
    is_offset_reached,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import CalDavConfigEntry
from .api import async_get_calendar_color, async_get_calendars
from .const import DOMAIN, TIMEOUT
from .coordinator import CalDavUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONF_CALENDARS = "calendars"
CONF_CUSTOM_CALENDARS = "custom_calendars"
CONF_CALENDAR = "calendar"
CONF_SEARCH = "search"
CONF_DAYS = "days"

# Number of days to look ahead for next event when configured by ConfigEntry
CONFIG_ENTRY_DEFAULT_DAYS = 7

# Only allow VCALENDARs that support this component type
SUPPORTED_COMPONENT = "VEVENT"

THIS_AND_FUTURE = "THISANDFUTURE"

PLATFORM_SCHEMA = CALENDAR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_URL): probatio.Url(),
        probatio.Optional(CONF_CALENDARS, default=[]): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
        probatio.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_PASSWORD), "authentication"): cv.string,
        probatio.Optional(CONF_CUSTOM_CALENDARS, default=[]): probatio.All(
            probatio.EnsureList(),
            [
                probatio.Schema(
                    {
                        probatio.Required(CONF_CALENDAR): cv.string,
                        probatio.Required(CONF_NAME): cv.string,
                        probatio.Required(CONF_SEARCH): cv.string,
                    }
                )
            ],
        ),
        probatio.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        probatio.Optional(CONF_DAYS, default=1): cv.positive_int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    disc_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the WebDav Calendar platform."""
    url = config[CONF_URL]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    days = config[CONF_DAYS]

    client = await hass.async_add_executor_job(
        partial(
            DAVClient,
            url,
            None,
            username,
            password,
            ssl_verify_cert=config[CONF_VERIFY_SSL],
            timeout=TIMEOUT,
        )
    )

    calendars = await async_get_calendars(hass, client, SUPPORTED_COMPONENT)

    entities = []
    device_id: str | None
    for calendar, calendar_name in calendars:
        # If a calendar name was given in the configuration,
        # ignore all the others
        if config[CONF_CALENDARS] and calendar_name not in config[CONF_CALENDARS]:
            _LOGGER.debug("Ignoring calendar '%s'", calendar_name)
            continue

        # Create additional calendars based on custom filtering rules
        for cust_calendar in config[CONF_CUSTOM_CALENDARS]:
            # Check that the base calendar matches
            if cust_calendar[CONF_CALENDAR] != calendar_name:
                continue

            name = cust_calendar[CONF_NAME]
            device_id = f"{cust_calendar[CONF_CALENDAR]} {cust_calendar[CONF_NAME]}"
            entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
            coordinator = CalDavUpdateCoordinator(
                hass,
                None,
                calendar=calendar,
                calendar_name=calendar_name,
                days=days,
                include_all_day=True,
                search=cust_calendar[CONF_SEARCH],
            )
            entities.append(
                WebDavCalendarEntity(name, entity_id, coordinator, supports_offset=True)
            )

        # Create a default calendar if there was no custom one for all calendars
        # that support events.
        if not config[CONF_CUSTOM_CALENDARS]:
            name = calendar_name
            device_id = calendar_name
            entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
            coordinator = CalDavUpdateCoordinator(
                hass,
                None,
                calendar=calendar,
                calendar_name=calendar_name,
                days=days,
                include_all_day=False,
                search=None,
            )
            entities.append(
                WebDavCalendarEntity(name, entity_id, coordinator, supports_offset=True)
            )

    async_add_entities(entities, True)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalDavConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the CalDav calendar platform for a config entry."""
    calendars = await async_get_calendars(hass, entry.runtime_data, SUPPORTED_COMPONENT)
    entities = [
        WebDavCalendarEntity(
            calendar_name,
            async_generate_entity_id(ENTITY_ID_FORMAT, calendar_name, hass=hass),
            CalDavUpdateCoordinator(
                hass,
                entry,
                calendar=calendar,
                calendar_name=calendar_name,
                days=CONFIG_ENTRY_DEFAULT_DAYS,
                include_all_day=True,
                search=None,
            ),
            unique_id=f"{entry.entry_id}-{calendar.id}",
        )
        for calendar, calendar_name in calendars
        if calendar_name
    ]
    async_add_entities(entities, True)


class WebDavCalendarEntity(CoordinatorEntity[CalDavUpdateCoordinator], CalendarEntity):
    """A device for getting the next Task from a WebDav Calendar."""

    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(
        self,
        name: str | None,
        entity_id: str,
        coordinator: CalDavUpdateCoordinator,
        unique_id: str | None = None,
        supports_offset: bool = False,
    ) -> None:
        """Create the WebDav Calendar Event Device."""
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._event: CalendarEvent | None = None
        self._attr_name = name
        if unique_id is not None:
            self._attr_unique_id = unique_id
        if coordinator.search is not None:
            # Changes would not be checked against the filter
            self._attr_supported_features = CalendarEntityFeature.CREATE_EVENT
        self._supports_offset = supports_offset

    @override
    async def async_prepare_to_add_to_hass(self) -> None:
        """Read the server color of a calendar that has no entity yet.

        The color only applies when an entity is first registered.
        """
        await super().async_prepare_to_add_to_hass()
        if self.unique_id is None or er.async_get(self.hass).async_get_entity_id(
            self.platform.domain, self.platform.platform_name, self.unique_id
        ):
            return
        try:
            self._attr_initial_color = await async_get_calendar_color(
                self.hass, self.coordinator.calendar
            )
        except (caldav_requests.exceptions.RequestException, DAVError) as err:
            _LOGGER.debug("Cannot read the color of %s: %s", self.name, err)

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self.coordinator.async_get_events(hass, start_date, end_date)

    @override
    async def async_create_event(self, **kwargs: Any) -> None:
        """Create a new event in the calendar."""
        _LOGGER.debug("Event: %s", kwargs)

        item_data: dict[str, Any] = {
            "summary": kwargs["summary"],
            "dtstart": kwargs["dtstart"],
            "dtend": kwargs["dtend"],
        }
        if description := kwargs.get("description"):
            item_data["description"] = description
        if location := kwargs.get("location"):
            item_data["location"] = location
        if rrule := kwargs.get("rrule"):
            item_data["rrule"] = rrule

        _LOGGER.debug("ICS data %s", item_data)

        try:
            await self.hass.async_add_executor_job(
                partial(self.coordinator.calendar.add_event, **item_data),
            )
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(f"CalDAV save error: {err}") from err

    @override
    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Update an event, a recurring one as a whole."""
        # Checking a repeat rule can take a while, so it runs in the executor
        await self._async_call(
            self._update_event, uid, event, recurrence_id, recurrence_range
        )
        await self.coordinator.async_request_refresh()

    def _update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None,
        recurrence_range: str | None,
    ) -> None:
        """Check and save an update."""
        item = self._get_event(uid)
        calendar = item.icalendar_instance
        series = _get_series(calendar)
        _check_whole_event(series, recurrence_id, recurrence_range)
        if _same_times(series, event):
            # Leave the stored times as they are
            event = {
                key: value
                for key, value in event.items()
                if key not in (EVENT_START, EVENT_END)
            }
        _check_series_change(calendar, series, event)
        original_start = series.DTSTART
        _set_fields(series, event)
        if "RRULE" in series and (
            EVENT_RRULE in event or original_start != series.DTSTART
        ):
            _check_rule_start(series)
        # Otherwise save() merges just the first component into the stored
        # event when that one is an override
        item.save(only_this_recurrence=False)

    @override
    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event, a recurring one as a whole."""
        await self._async_call(self._delete_event, uid, recurrence_id, recurrence_range)
        await self.coordinator.async_request_refresh()

    def _delete_event(
        self, uid: str, recurrence_id: str | None, recurrence_range: str | None
    ) -> None:
        """Check and delete an event."""
        item = self._get_event(uid)
        calendar = item.icalendar_instance
        _check_whole_event(_get_series(calendar), recurrence_id, recurrence_range)
        # Only delete the version that was checked; If-Match can't use a weak ETag
        etag = item.etag
        if_match = bool(etag and not etag.startswith("W/"))
        item.delete(if_match=if_match, precondition="etag")

    def _get_event(self, uid: str) -> Event:
        """Fetch the CalDAV object holding an event and its overrides."""
        return cast(Event, self.coordinator.calendar.get_event_by_uid(uid))

    async def _async_call[_T](self, target: Callable[..., _T], *args: Any) -> _T:
        """Run a CalDAV request in the executor."""
        try:
            return await self.hass.async_add_executor_job(target, *args)
        except NotFoundError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="event_not_found"
            ) from err
        except (ETagMismatchError, ScheduleTagMismatchError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="event_changed"
            ) from err
        except (
            caldav_requests.exceptions.ConnectionError,
            caldav_requests.exceptions.Timeout,
            DAVError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request_error"
            ) from err

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update event data."""
        self._event = self.coordinator.data
        if self._supports_offset:
            self._attr_extra_state_attributes = {
                "offset_reached": is_offset_reached(
                    self._event.start_datetime_local,
                    self.coordinator.offset,  # type: ignore[arg-type]
                )
                if self._event
                else False
            }
        super()._handle_coordinator_update()

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()


def _get_series(calendar: icalendar.Calendar) -> icalendar.Event:
    """Return the main component of an event, which may follow its overrides."""
    components = calendar.walk("VEVENT")
    return next(
        (component for component in components if "RECURRENCE-ID" not in component),
        components[0],
    )


def _check_whole_event(
    series: icalendar.Event, recurrence_id: str | None, recurrence_range: str | None
) -> None:
    """Refuse changes to single occurrences of a recurring event.

    A change from the first occurrence on is a change to the whole event. The
    recurrence id is the occurrence start as the coordinator formats it.
    """
    if not recurrence_id:
        return
    start: date | datetime
    try:
        start = date.fromisoformat(recurrence_id)
    except ValueError:
        start = datetime.fromisoformat(recurrence_id)
    if (
        recurrence_range != THIS_AND_FUTURE
        or "RECURRENCE-ID" in series
        or not _same_time(start, series.DTSTART)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="occurrence_not_supported"
        )


def _same_times(series: icalendar.Event, event: dict[str, Any]) -> bool:
    """Return if an update keeps the start and end of the event."""
    try:
        end = series.end
    except ValueError:
        # The event has no consistent end, so the update sets one
        return False
    return _same_time(event[EVENT_START], series.DTSTART) and _same_time(
        event[EVENT_END], end
    )


def _same_time(value: date | datetime, other: date | datetime) -> bool:
    """Return if two starts or ends are the same, whatever their time zones."""
    return _instant(value) == _instant(other)


def _instant(value: date | datetime) -> date | datetime:
    """Return a value that compares by instant, taking floating times as local."""
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    # Times in a repeated hour only compare by instant within one time zone
    return value.astimezone(UTC)


def _check_series_change(
    calendar: icalendar.Calendar, series: icalendar.Event, event: dict[str, Any]
) -> None:
    """Refuse changes the recurrence of a series can't follow."""
    if "RRULE" not in series and "RDATE" not in series:
        return
    rrule = event.get(EVENT_RRULE)
    if EVENT_START not in event and not rrule:
        return
    start = event.get(EVENT_START, series.DTSTART)
    # UNTIL, EXDATE and RECURRENCE-ID keep the type of the old start
    if isinstance(start, datetime) != isinstance(series.DTSTART, datetime):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="all_day_change_not_supported"
        )
    start = _in_time_basis(start, series.DTSTART)
    # Changed and deleted occurrences are tied to the old start and rule
    has_exceptions = (
        "EXDATE" in series or "RDATE" in series or len(calendar.walk("VEVENT")) > 1
    )
    if has_exceptions and (
        start != series.DTSTART
        or (
            rrule
            and ("RRULE" not in series or _parse_rule(rrule, start) != series["RRULE"])
        )
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="exceptions_change_not_supported"
        )


def _occurrences(series: icalendar.Event) -> rrulebase:
    """Return the occurrences the rule of a series produces, as datetimes."""
    start = series.DTSTART
    rule = _parse_rule(series["RRULE"].to_ical().decode(), start)
    if not isinstance(start, datetime):
        start = datetime.combine(start, time())
    return rrulestr(rule.to_ical().decode(), dtstart=start)


def _check_rule_start(series: icalendar.Event) -> None:
    """Refuse a series whose start isn't one of the times its rule produces."""
    start = series.DTSTART
    if not isinstance(start, datetime):
        start = datetime.combine(start, time())
    try:
        first = _occurrences(series).after(start, inc=True)
    except ValueError:
        first = None
    if first != start:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="start_not_in_rule"
        )


def _parse_rule(rrule: str, start: date | datetime) -> icalendar.vRecur:
    """Parse a repeat rule, with UNTIL in the form the start needs.

    UNTIL is a date for all-day events, floating for floating events and UTC
    otherwise. Without a time zone it is in Home Assistant's, as the frontend
    sends it.
    """
    rule = icalendar.vRecur.from_ical(rrule)
    if not (until := rule.get("UNTIL")):
        return rule
    value = until[0]
    if not isinstance(start, datetime):
        if isinstance(value, datetime):
            value = dt_util.as_local(value).date() if value.tzinfo else value.date()
    else:
        if not isinstance(value, datetime):
            value = datetime.combine(value, time(23, 59, 59))
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_util.get_default_time_zone())
        if start.tzinfo is None:
            value = dt_util.as_local(value).replace(tzinfo=None)
        else:
            value = value.astimezone(UTC)
    rule["UNTIL"] = [value]
    return rule


def _in_time_basis(
    value: date | datetime, original_start: date | datetime
) -> date | datetime:
    """Return a time from Home Assistant in the time zone the event uses.

    Times come in Home Assistant's time zone. A floating event keeps the wall time.
    """
    if not isinstance(value, datetime):
        return value
    if isinstance(original_start, datetime) and original_start.tzinfo is None:
        return value.replace(tzinfo=None)
    # A time skipped when daylight saving time starts doesn't exist
    if value.astimezone(UTC).astimezone(value.tzinfo).replace(
        tzinfo=None
    ) != value.replace(tzinfo=None):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="daylight_saving_time"
        )
    if not isinstance(original_start, datetime):
        return value
    converted = value.astimezone(original_start.tzinfo)
    # A TZID time in the hour that repeats always means the first one
    if (
        converted.fold
        and converted.replace(fold=0).utcoffset() != converted.utcoffset()
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="daylight_saving_time"
        )
    return converted


def _set_fields(series: icalendar.Event, event: dict[str, Any]) -> None:
    """Set the fields of an update, keeping any field it leaves out."""
    original_start = series.DTSTART
    # Keep the name of the time zone, which may not be an IANA one
    tzid = series["DTSTART"].params.get("TZID")
    for key in (
        EVENT_SUMMARY,
        EVENT_START,
        EVENT_END,
        EVENT_DESCRIPTION,
        EVENT_LOCATION,
    ):
        if key in event:
            value = event[key]
            if key in (EVENT_START, EVENT_END):
                value = _in_time_basis(value, original_start)
            series.pop(key)
            if value:
                keep_tzid = (
                    tzid
                    and isinstance(value, datetime)
                    and value.tzinfo == original_start.tzinfo
                )
                series.add(key, value, parameters={"TZID": tzid} if keep_tzid else None)
    if EVENT_END in event:
        # DTEND replaces a DURATION
        series.pop("DURATION")
    if rrule := event.get(EVENT_RRULE):
        series.pop("RRULE")
        series.add("RRULE", _parse_rule(rrule, series.DTSTART))
    elif "UNTIL" in series.get("RRULE", {}) and original_start != series.DTSTART:
        # Move the end of the rule along, so no occurrence is lost
        rule = _parse_rule(series["RRULE"].to_ical().decode(), original_start)
        rule["UNTIL"] = [_shift(rule["UNTIL"][0], original_start, series.DTSTART)]
        series["RRULE"] = rule


def _shift(
    value: date | datetime, start: date | datetime, new_start: date | datetime
) -> date | datetime:
    """Move a time by as much wall time as the start moved, in its time zone."""
    if not isinstance(start, datetime):
        # All-day, so UNTIL is a date too
        return value + timedelta(days=new_start.toordinal() - start.toordinal())
    new_start = cast(datetime, new_start)
    zone = start.tzinfo
    wall = cast(datetime, value)
    if zone:
        wall = wall.astimezone(zone).replace(tzinfo=None)
    wall += new_start.replace(tzinfo=None) - start.replace(tzinfo=None)
    return wall.replace(tzinfo=zone).astimezone(UTC) if zone else wall
