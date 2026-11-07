"""Support for WebDav Calendar."""

from collections.abc import Callable
from datetime import date, datetime
from functools import partial
import logging
from typing import Any, cast, override

from caldav.calendarobjectresource import Event
from caldav.davclient import DAVClient
from caldav.lib.error import DAVError, NotFoundError
from caldav.lib.http_sync import requests as caldav_requests
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
        item = await self._async_get_event(uid)
        series = _get_series(item.icalendar_instance)
        _check_whole_event(series, recurrence_id, recurrence_range)
        _set_fields(series, event)
        await self._async_save(item)
        await self.coordinator.async_request_refresh()

    @override
    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event, a recurring one as a whole."""
        item = await self._async_get_event(uid)
        _check_whole_event(
            _get_series(item.icalendar_instance), recurrence_id, recurrence_range
        )
        await self._async_call(item.delete)
        await self.coordinator.async_request_refresh()

    async def _async_save(self, item: Event) -> None:
        """Save a changed event with all its components."""
        # Otherwise save() merges just the first component into the stored
        # event when that one is an override
        await self._async_call(partial(item.save, only_this_recurrence=False))

    async def _async_get_event(self, uid: str) -> Event:
        """Fetch the CalDAV object holding an event and its overrides."""
        return cast(
            Event,
            await self._async_call(self.coordinator.calendar.get_event_by_uid, uid),
        )

    async def _async_call[_T](self, target: Callable[..., _T], *args: Any) -> _T:
        """Run a CalDAV request in the executor."""
        try:
            return await self.hass.async_add_executor_job(target, *args)
        except NotFoundError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="event_not_found"
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
        or start > series.DTSTART
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="occurrence_not_supported"
        )


def _set_fields(series: icalendar.Event, event: dict[str, Any]) -> None:
    """Set the fields of an update, keeping any field it leaves out."""
    for key in (
        EVENT_SUMMARY,
        EVENT_START,
        EVENT_END,
        EVENT_DESCRIPTION,
        EVENT_LOCATION,
    ):
        if key in event:
            series.pop(key)
            if value := event[key]:
                series.add(key, value)
    # DTEND is always set, so the event must not keep a DURATION
    series.pop("DURATION")
    if rrule := event.get(EVENT_RRULE):
        series.pop("RRULE")
        series.add("RRULE", icalendar.vRecur.from_ical(rrule))
