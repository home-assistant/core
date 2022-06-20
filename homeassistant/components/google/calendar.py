"""Support for Google Calendar Search binary sensors."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
import logging
from typing import Any

from gcal_sync.api import GoogleCalendarService, ListEventsRequest
from gcal_sync.exceptions import ApiException
from gcal_sync.model import DateOrDatetime, Event
import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    CalendarEntity,
    CalendarEvent,
    extract_offset,
    is_offset_reached,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_ENTITIES, CONF_NAME, CONF_OFFSET
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import (
    CONF_IGNORE_AVAILABILITY,
    CONF_SEARCH,
    CONF_TRACK,
    DATA_SERVICE,
    DEFAULT_CONF_OFFSET,
    DOMAIN,
    YAML_DEVICES,
    get_calendar_info,
    load_config,
    update_config,
)
from .api import get_feature_access
from .const import (
    EVENT_DESCRIPTION,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    EVENT_TYPES_CONF,
    FeatureAccess,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

# Events have a transparency that determine whether or not they block time on calendar.
# When an event is opaque, it means "Show me as busy" which is the default.  Events that
# are not opaque are ignored by default.
OPAQUE = "opaque"

_EVENT_IN_TYPES = vol.Schema(
    {
        vol.Exclusive(EVENT_IN_DAYS, EVENT_TYPES_CONF): cv.positive_int,
        vol.Exclusive(EVENT_IN_WEEKS, EVENT_TYPES_CONF): cv.positive_int,
    }
)

SERVICE_CREATE_EVENT = "create_event"
CREATE_EVENT_SCHEMA = vol.All(
    cv.has_at_least_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.has_at_most_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.make_entity_service_schema(
        {
            vol.Required(EVENT_SUMMARY): cv.string,
            vol.Optional(EVENT_DESCRIPTION, default=""): cv.string,
            vol.Inclusive(
                EVENT_START_DATE, "dates", "Start and end dates must both be specified"
            ): cv.date,
            vol.Inclusive(
                EVENT_END_DATE, "dates", "Start and end dates must both be specified"
            ): cv.date,
            vol.Inclusive(
                EVENT_START_DATETIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            vol.Inclusive(
                EVENT_END_DATETIME,
                "datetimes",
                "Start and end datetimes must both be specified",
            ): cv.datetime,
            vol.Optional(EVENT_IN): _EVENT_IN_TYPES,
        }
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the google calendar platform."""
    calendar_service = hass.data[DOMAIN][DATA_SERVICE]
    try:
        result = await calendar_service.async_list_calendars()
    except ApiException as err:
        raise PlatformNotReady(str(err)) from err

    # Yaml configuration may override objects from the API
    calendars = await hass.async_add_executor_job(
        load_config, hass.config.path(YAML_DEVICES)
    )
    new_calendars = []
    entities = []
    for calendar_item in result.items:
        calendar_id = calendar_item.id
        if calendars and calendar_id in calendars:
            calendar_info = calendars[calendar_id]
        else:
            calendar_info = get_calendar_info(
                hass, calendar_item.dict(exclude_unset=True)
            )
            new_calendars.append(calendar_info)

        # Yaml calendar config may map one calendar to multiple entities with extra options like
        # offsets or search criteria.
        num_entities = len(calendar_info[CONF_ENTITIES])
        for data in calendar_info[CONF_ENTITIES]:
            entity_enabled = data.get(CONF_TRACK, True)
            if not entity_enabled:
                _LOGGER.warning(
                    "The 'track' option in google_calendars.yaml has been deprecated. The setting "
                    "has been imported to the UI, and should now be removed from google_calendars.yaml"
                )
            entity_name = data[CONF_DEVICE_ID]
            entities.append(
                GoogleCalendarEntity(
                    calendar_service,
                    calendar_id,
                    data,
                    generate_entity_id(ENTITY_ID_FORMAT, entity_name, hass=hass),
                    # The google_calendars.yaml file lets users add multiple entities for
                    # the same calendar id and needs additional disambiguation
                    f"{calendar_id}-{entity_name}" if num_entities > 1 else calendar_id,
                    entity_enabled,
                )
            )

    async_add_entities(entities, True)

    if calendars and new_calendars:

        def append_calendars_to_config() -> None:
            path = hass.config.path(YAML_DEVICES)
            for calendar in new_calendars:
                update_config(path, calendar)

        await hass.async_add_executor_job(append_calendars_to_config)

    platform = entity_platform.async_get_current_platform()
    if get_feature_access(hass, entry) is FeatureAccess.read_write:
        platform.async_register_entity_service(
            SERVICE_CREATE_EVENT,
            CREATE_EVENT_SCHEMA,
            async_create_event,
        )


class GoogleCalendarEntity(CalendarEntity):
    """A calendar event device."""

    def __init__(
        self,
        calendar_service: GoogleCalendarService,
        calendar_id: str,
        data: dict[str, Any],
        entity_id: str,
        unique_id: str,
        entity_enabled: bool,
    ) -> None:
        """Create the Calendar event device."""
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self._search: str | None = data.get(CONF_SEARCH)
        self._ignore_availability: bool = data.get(CONF_IGNORE_AVAILABILITY, False)
        self._event: CalendarEvent | None = None
        self._name: str = data[CONF_NAME]
        self._offset = data.get(CONF_OFFSET, DEFAULT_CONF_OFFSET)
        self._offset_value: timedelta | None = None
        self.entity_id = entity_id
        self._attr_unique_id = unique_id
        self._attr_entity_registry_enabled_default = entity_enabled

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Return the device state attributes."""
        return {"offset_reached": self.offset_reached}

    @property
    def offset_reached(self) -> bool:
        """Return whether or not the event offset was reached."""
        if self._event and self._offset_value:
            return is_offset_reached(
                self._event.start_datetime_local, self._offset_value
            )
        return False

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    def _event_filter(self, event: Event) -> bool:
        """Return True if the event is visible."""
        if self._ignore_availability:
            return True
        return event.transparency == OPAQUE

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""

        request = ListEventsRequest(
            calendar_id=self.calendar_id,
            start_time=start_date,
            end_time=end_date,
            search=self._search,
        )
        result_items = []
        try:
            result = await self.calendar_service.async_list_events(request)
            async for result_page in result:
                result_items.extend(result_page.items)
        except ApiException as err:
            _LOGGER.error("Unable to connect to Google: %s", err)
            return []
        return [
            _get_calendar_event(event)
            for event in filter(self._event_filter, result_items)
        ]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest data."""
        request = ListEventsRequest(calendar_id=self.calendar_id, search=self._search)
        try:
            result = await self.calendar_service.async_list_events(request)
        except ApiException as err:
            _LOGGER.error("Unable to connect to Google: %s", err)
            return

        # Pick the first visible event and apply offset calculations.
        valid_items = filter(self._event_filter, result.items)
        event = copy.deepcopy(next(valid_items, None))
        if event:
            (event.summary, offset) = extract_offset(event.summary, self._offset)
            self._event = _get_calendar_event(event)
            self._offset_value = offset
        else:
            self._event = None


def _get_calendar_event(event: Event) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    return CalendarEvent(
        summary=event.summary,
        start=event.start.value,
        end=event.end.value,
        description=event.description,
        location=event.location,
    )


async def async_create_event(entity: GoogleCalendarEntity, call: ServiceCall) -> None:
    """Add a new event to calendar."""
    start: DateOrDatetime | None = None
    end: DateOrDatetime | None = None
    hass = entity.hass

    if EVENT_IN in call.data:
        if EVENT_IN_DAYS in call.data[EVENT_IN]:
            now = datetime.now()

            start_in = now + timedelta(days=call.data[EVENT_IN][EVENT_IN_DAYS])
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

        elif EVENT_IN_WEEKS in call.data[EVENT_IN]:
            now = datetime.now()

            start_in = now + timedelta(weeks=call.data[EVENT_IN][EVENT_IN_WEEKS])
            end_in = start_in + timedelta(days=1)

            start = DateOrDatetime(date=start_in)
            end = DateOrDatetime(date=end_in)

    elif EVENT_START_DATE in call.data and EVENT_END_DATE in call.data:
        start = DateOrDatetime(date=call.data[EVENT_START_DATE])
        end = DateOrDatetime(date=call.data[EVENT_END_DATE])

    elif EVENT_START_DATETIME in call.data and EVENT_END_DATETIME in call.data:
        start_dt = call.data[EVENT_START_DATETIME]
        end_dt = call.data[EVENT_END_DATETIME]
        start = DateOrDatetime(date_time=start_dt, timezone=str(hass.config.time_zone))
        end = DateOrDatetime(date_time=end_dt, timezone=str(hass.config.time_zone))

    if start is None or end is None:
        raise ValueError("Missing required fields to set start or end date/datetime")

    await entity.calendar_service.async_create_event(
        entity.calendar_id,
        Event(
            summary=call.data[EVENT_SUMMARY],
            description=call.data[EVENT_DESCRIPTION],
            start=start,
            end=end,
        ),
    )
