"""Support for WebDav Calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import Any

import caldav
from ical.types import Range
from icalendar import vDDDTypes
import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    EVENT_RRULE,
    EVENT_START,
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CalDavConfigEntry
from .api import async_get_calendars
from .const import CONF_READ_ONLY
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

# Platform configuration is out-dated in my understanding, the lines below will
# eventually be removed. Config entries are used instead.
# Keep them here for reference until then.
# -------------------------------------------------
PLATFORM_SCHEMA = CALENDAR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): vol.Url(),
        vol.Optional(CONF_CALENDARS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_CUSTOM_CALENDARS, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_CALENDAR): cv.string,
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_SEARCH): cv.string,
                    }
                )
            ],
        ),
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
        vol.Optional(CONF_DAYS, default=1): cv.positive_int,
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

    client = caldav.DAVClient(
        url, None, username, password, ssl_verify_cert=config[CONF_VERIFY_SSL]
    )

    calendars = await async_get_calendars(hass, client, SUPPORTED_COMPONENT)

    entities = []
    device_id: str | None
    for calendar in list(calendars):
        # If a calendar name was given in the configuration,
        # ignore all the others
        if config[CONF_CALENDARS] and calendar.name not in config[CONF_CALENDARS]:
            _LOGGER.debug("Ignoring calendar '%s'", calendar.name)
            continue

        # Create additional calendars based on custom filtering rules
        for cust_calendar in config[CONF_CUSTOM_CALENDARS]:
            # Check that the base calendar matches
            if cust_calendar[CONF_CALENDAR] != calendar.name:
                continue

            name = cust_calendar[CONF_NAME]
            device_id = f"{cust_calendar[CONF_CALENDAR]} {cust_calendar[CONF_NAME]}"
            entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
            coordinator = CalDavUpdateCoordinator(
                hass,
                None,
                calendar=calendar,
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
            name = calendar.name
            device_id = calendar.name
            entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
            coordinator = CalDavUpdateCoordinator(
                hass,
                None,
                calendar=calendar,
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
    async_add_entities(
        new_entities=(
            WebDavCalendarEntity(
                f"{entry.data[CONF_USERNAME].capitalize()} {calendar.name}",  # default entity name is USERNAME calendar.name so the user can better distinguish between calendars.
                async_generate_entity_id(
                    ENTITY_ID_FORMAT,
                    f"{entry.data[CONF_URL]} {entry.data[CONF_USERNAME]} {calendar.name}",  # entity_id based on URL, USERNAME and calendarname to identify a calendar uniquely
                    hass=hass,
                ),
                CalDavUpdateCoordinator(
                    hass,
                    entry,
                    calendar=calendar,
                    days=CONFIG_ENTRY_DEFAULT_DAYS,
                    include_all_day=True,
                    search=None,
                ),
                unique_id=f"{entry.entry_id}-{calendar.id}",
                read_only=entry.data.get(CONF_READ_ONLY, False),
            )
            for calendar in calendars
            if calendar.name
        ),
        update_before_add=True,
    )


class WebDavCalendarEntity(CoordinatorEntity[CalDavUpdateCoordinator], CalendarEntity):
    """A device for getting the next Task from a WebDav Calendar."""

    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(
        self,
        name: str | None,
        entity_id: str,
        coordinator: CalDavUpdateCoordinator,
        unique_id: str | None = None,
        supports_offset: bool = False,
        read_only: bool = False,
    ) -> None:
        """Create the WebDav Calendar Event Device."""
        super().__init__(coordinator)
        self.entity_id = entity_id
        self._event: CalendarEvent | None = None
        self._attr_name = name
        if unique_id is not None:
            self._attr_unique_id = unique_id
        self._supports_offset = supports_offset
        if read_only:
            self._attr_supported_features = CalendarEntityFeature(0)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self.coordinator.async_get_events(hass, start_date, end_date)

    async def _async_create_event(self, **kwargs: Any) -> caldav.Event:
        """Add a new event to calendar."""

        def save_event() -> caldav.Event:
            return self.coordinator.calendar.save_event(**kwargs)

        event = await self.hass.async_add_executor_job(save_event)

        assert event is not None

        return event

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""

        await self._async_create_event(**kwargs)

        await self.async_update_ha_state(force_refresh=True)

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar.

        Supports deleting
        - a single event,
        - a recurring event,
        - a single occurrence of a recurring event,
        - an occurrence and all future occurrences of a recurring event.
        """

        # Home Assistant currently supportsyonly THIS_AND_FUTURE. In this case we need to delete the event specified by the recurrence_id and all future events in the series
        # We'll realiize this by updating the RRULE attribute UNTIL attribute to the datetime of the given recurrence.
        # With nextcloud the recurrence_id is already a date or datetime so we can use this directly as the cutoff date(-time) for the RRULE.
        if recurrence_range == Range.THIS_AND_FUTURE:
            # Get the master event of the series by uid
            master_event = await self.coordinator.async_get_event(self.hass, uid)
            if master_event is None:
                _LOGGER.error("Event with uid %s not found", uid)
                return

            assert hasattr(master_event, "icalendar_component")  # for mypy

            # Validate recurrence_id is provided
            if not recurrence_id:
                _LOGGER.error(
                    "The recurrence_id must be provided when recurrence_range is THIS_AND_FUTURE"
                )
                return

            # Parse recurrence_id
            recurrence_datetime = self.coordinator.parse_recurrence_id(recurrence_id)

            # Get the start date of the master event
            start_master = master_event.icalendar_component[EVENT_START].dt

            # If the start is a date, convert it to a datetime at midnight
            if isinstance(start_master, date) and not isinstance(
                start_master, datetime
            ):
                start_master = datetime.combine(start_master, time())

            # 2 possible ways to go from here:
            # If the recurrence_datetime is the same as the start of the master event, delete the entire series
            if recurrence_datetime <= start_master:
                _LOGGER.debug(
                    "The recurrence_id %s is the same or before the start of the master event %s. Deleting the entire series",
                    recurrence_datetime,
                    start_master,
                )

                def delete_event() -> None:
                    assert master_event is not None  # Mypy sucks. OK, probably my fault
                    master_event.delete()

                # Delete the master event, which will delete the entire series
                await self.hass.async_add_executor_job(delete_event)

            # Otherwise, modify the RRULE of the master event to set the UNTIL
            # attribute to before the recurrence_datetime to only delete the
            # given recurerence and all following recurrences
            else:
                _LOGGER.debug(
                    "The recurrence_id %s is after the start of the master event %s. Updating the RRULE to set the UNTIL attribute to before the recurrence_id to delete this and all future events",
                    recurrence_datetime,
                    start_master,
                )
                # Get the RRULE of the master event
                rrule = master_event.icalendar_component.get(EVENT_RRULE)
                if not rrule:
                    _LOGGER.error("The event with uid %s is not a recurring event", uid)
                    return
                # Change the UNTIL attribute to the recurrence_datetime - 1 day to exclude the recurrence itself
                rrule["until"] = recurrence_datetime - timedelta(days=1)
                rrule.pop("count")  # Remove COUNT if present
                master_event.icalendar_component[EVENT_RRULE] = rrule

                def update_event() -> None:
                    assert master_event is not None  # Mypy sucks. OK, probably my fault
                    master_event.save()

                # Write updated master event back to the calendar
                await self.hass.async_add_executor_job(update_event)

        # Delete only the specified occurrence of the series
        # This is done by adding an EXDATE to the master event
        elif recurrence_id is not None:
            # Get the master event of the series by uid
            master_event = await self.coordinator.async_get_event(self.hass, uid)
            if not master_event:
                _LOGGER.error("Event with uid %s not found", uid)
                return

            assert hasattr(master_event, "icalendar_component")  # for mypy

            # Create an Exception date (EXDATE) for the given recurrence_id
            master_event.icalendar_component.add(
                "EXDATE", vDDDTypes(self.coordinator.parse_recurrence_id(recurrence_id))
            )

            def update_master_event() -> None:
                master_event.save()

            # Delete the event by updating the master event with the newly added EXDATE
            await self.hass.async_add_executor_job(update_master_event)

        # No recurrence, delete the event by uid
        else:
            event = await self.coordinator.async_get_event(self.hass, uid)
            if not event:
                _LOGGER.error("Event with uid %s not found", uid)
                return

            def delete_event() -> None:
                event.delete()

            # Delete the event
            await self.hass.async_add_executor_job(delete_event)

        await self.async_update_ha_state(force_refresh=True)

    @callback
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

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
