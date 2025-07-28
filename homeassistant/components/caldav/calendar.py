"""Support for WebDav Calendar."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
import uuid

import caldav
from dateutil.parser import parse as date_parse
import icalendar
import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
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
from homeassistant.exceptions import HomeAssistantError
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
        (
            WebDavCalendarEntity(
                calendar.name,
                async_generate_entity_id(ENTITY_ID_FORMAT, calendar.name, hass=hass),
                CalDavUpdateCoordinator(
                    hass,
                    entry,
                    calendar=calendar,
                    days=CONFIG_ENTRY_DEFAULT_DAYS,
                    include_all_day=True,
                    search=None,
                ),
                unique_id=f"{entry.entry_id}-{calendar.id}",
            )
            for calendar in calendars
            if calendar.name
        ),
        True,
    )


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

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self.coordinator.async_get_events(hass, start_date, end_date)

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

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""
        try:
            # Convert parameters to CalDAV format
            event_data = _convert_event_params_to_dict(**kwargs)

            def _create_event() -> None:
                """Create event in CalDAV calendar."""
                calendar = self.coordinator.calendar
                # Try using save_event with parameters first, fallback to iCalendar string
                try:
                    calendar.save_event(**event_data)
                except (TypeError, AttributeError):
                    # Fallback to iCalendar string format
                    event_ical = _convert_event_params_to_ical(**kwargs)
                    calendar.save_event(event_ical)

            await self.hass.async_add_executor_job(_create_event)

        except Exception as err:
            _LOGGER.error("Error creating calendar event: %s", err)
            raise HomeAssistantError(f"Unable to create event: {err}") from err

        # Refresh coordinator data to show new event
        await self.coordinator.async_request_refresh()

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        try:
            def _delete_event() -> None:
                """Delete event from CalDAV calendar."""
                event_obj = _find_event_by_uid(self.coordinator.calendar, uid)

                if recurrence_id is not None:
                    # Handle recurring event modification
                    # For recurrence_id, we need to either delete a specific instance or create an exception
                    if recurrence_range == "THIS_AND_FUTURE":
                        # Modify the original event to end before this instance
                        _modify_recurring_event_until(event_obj, recurrence_id)
                    else:
                        # Delete just this instance by adding an EXDATE to the series
                        _add_exception_to_recurring_event(event_obj, recurrence_id)
                else:
                    # Delete the entire event or event series
                    event_obj.delete()

            await self.hass.async_add_executor_job(_delete_event)

        except Exception as err:
            raise HomeAssistantError(f"Unable to delete event: {err}") from err

        # Refresh coordinator data to remove deleted event
        await self.coordinator.async_request_refresh()

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Update an existing event on the calendar."""
        try:
            def _update_event() -> None:
                """Update event in CalDAV calendar."""
                event_obj = _find_event_by_uid(self.coordinator.calendar, uid)

                if recurrence_id is not None:
                    # Handle recurring event modification
                    if recurrence_range == "THIS_AND_FUTURE":
                        # Split the series: truncate original and create new series
                        _split_recurring_event_series(event_obj, event, recurrence_id)
                    else:
                        # Create exception for single instance
                        _create_recurring_event_exception(event_obj, event, recurrence_id)
                else:
                    # Update the entire event or event series
                    _update_event_data(event_obj, event)

            await self.hass.async_add_executor_job(_update_event)

        except Exception as err:
            raise HomeAssistantError(f"Unable to update event: {err}") from err

        # Refresh coordinator data to show updated event
        await self.coordinator.async_request_refresh()


def _convert_event_params_to_dict(**kwargs: Any) -> dict[str, Any]:
    """Convert Home Assistant event parameters to CalDAV parameter format.

    This attempts to use direct parameter passing similar to save_todo().
    """
    event_data: dict[str, Any] = {}

    # Handle summary
    if 'summary' in kwargs:
        event_data['summary'] = kwargs['summary']

    # Handle start/end times (using RFC5545 field names)
    if 'dtstart' in kwargs:
        event_data['dtstart'] = kwargs['dtstart']

    if 'dtend' in kwargs:
        event_data['dtend'] = kwargs['dtend']

    # Handle optional fields
    if kwargs.get('description'):
        event_data['description'] = kwargs['description']

    if kwargs.get('location'):
        event_data['location'] = kwargs['location']

    # Handle UID
    if 'uid' in kwargs:
        event_data['uid'] = kwargs['uid']
    else:
        event_data['uid'] = str(uuid.uuid4())

    return event_data


def _convert_event_params_to_ical(**kwargs: Any) -> str:
    """Convert Home Assistant event parameters to iCalendar format.

    This is the fallback method that creates iCalendar strings.
    Uses RFC5545 field names as received from the calendar service.
    """
    calendar = icalendar.Calendar()
    calendar.add('prodid', '-//Home Assistant//CalDAV//EN')
    calendar.add('version', '2.0')

    event = icalendar.Event()

    # Handle start/end times (using RFC5545 field names)
    if 'dtstart' in kwargs:
        event.add('dtstart', kwargs['dtstart'])

    if 'dtend' in kwargs:
        event.add('dtend', kwargs['dtend'])

    # Required fields
    if 'summary' in kwargs:
        event.add('summary', kwargs['summary'])

    # Optional fields
    if kwargs.get('description'):
        event.add('description', kwargs['description'])

    if kwargs.get('location'):
        event.add('location', kwargs['location'])

    # Generate a UID if not provided
    if 'uid' not in kwargs:
        event.add('uid', str(uuid.uuid4()))
    else:
        event.add('uid', kwargs['uid'])

    # Add timestamp
    event.add('dtstamp', datetime.now().astimezone())

    calendar.add_component(event)
    return calendar.to_ical().decode('utf-8')


def _find_event_by_uid(calendar: caldav.Calendar, uid: str) -> caldav.CalendarObjectResource:
    """Find an event by UID using existing search patterns.

    This reuses the same search pattern used by the coordinator.
    """
    events = calendar.search(event=True, expand=False)

    for event_obj in events:
        if hasattr(event_obj.instance, "vevent"):
            vevent = event_obj.instance.vevent
            if hasattr(vevent, "uid") and vevent.uid.value == uid:
                return event_obj

    raise ValueError(f"Event with UID {uid} not found")


def _modify_recurring_event_until(event_obj: caldav.CalendarObjectResource, recurrence_id: str) -> None:
    """Modify a recurring event to end before the specified recurrence ID."""
    try:
        # Parse the recurrence_id as a datetime to set as UNTIL
        until_date = date_parse(recurrence_id)

        # Get the event data and modify the RRULE
        vevent = event_obj.instance.vevent

        if hasattr(vevent, 'rrule'):
            # Parse existing RRULE and add UNTIL
            rrule_str = str(vevent.rrule.value)
            if 'UNTIL=' not in rrule_str:
                # Add UNTIL to the RRULE
                rrule_str += f";UNTIL={until_date.strftime('%Y%m%dT%H%M%SZ')}"
                # Update the RRULE
                vevent.rrule.value = rrule_str
                event_obj.save()
        else:
            # No RRULE found, just delete the single event
            event_obj.delete()

    except (ValueError, AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to modify recurring event until date: %s", err)
        # Fallback to deleting the entire series
        event_obj.delete()


def _add_exception_to_recurring_event(event_obj: caldav.CalendarObjectResource, recurrence_id: str) -> None:
    """Add an exception date (EXDATE) to a recurring event."""
    try:
        exception_date = date_parse(recurrence_id)

        vevent = event_obj.instance.vevent

        # Add EXDATE to exclude this specific instance
        if hasattr(vevent, 'exdate'):
            # Add to existing EXDATE list
            if hasattr(vevent.exdate, 'value'):
                if isinstance(vevent.exdate.value, list):
                    vevent.exdate.value.append(exception_date)
                else:
                    vevent.exdate.value = [vevent.exdate.value, exception_date]
        else:
            # Create new EXDATE
            vevent.add('exdate', exception_date)

        event_obj.save()

    except (ValueError, AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to add exception to recurring event: %s", err)
        # Fallback to deleting the entire series
        event_obj.delete()


def _split_recurring_event_series(event_obj: caldav.CalendarObjectResource, event_data: dict[str, Any], recurrence_id: str) -> None:
    """Split a recurring event series at the specified recurrence ID."""
    try:
        split_date = date_parse(recurrence_id)

        # First, modify the original series to end before the split date
        _modify_recurring_event_until(event_obj, recurrence_id)

        # Then create a new series starting from the split date
        new_event_data = _convert_event_params_to_ical(**event_data)
        # Parse and modify the start date to match recurrence_id
        new_event = icalendar.Calendar.from_ical(new_event_data)

        for component in new_event.walk():
            if component.name == "VEVENT":
                component['dtstart'] = split_date
                # Adjust end time accordingly
                if 'dtend' in component:
                    duration = component['dtend'].dt - component['dtstart'].dt
                    component['dtend'] = split_date + duration
                # Generate new UID for the new series
                component['uid'] = str(uuid.uuid4())

        # Save the new series
        event_obj.calendar.save_event(new_event.to_ical().decode('utf-8'))

    except (ValueError, AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to split recurring event series: %s", err)
        # Fallback to updating the entire series
        _update_event_data(event_obj, event_data)


def _create_recurring_event_exception(event_obj: caldav.CalendarObjectResource, event_data: dict[str, Any], recurrence_id: str) -> None:
    """Create an exception event for a single instance of a recurring series."""
    try:
        exception_date = date_parse(recurrence_id)

        # First, add the exception date to the original series
        _add_exception_to_recurring_event(event_obj, recurrence_id)

        # Then create a new single event for this exception
        exception_event_data = dict(event_data)
        exception_event_data['dtstart'] = exception_date

        # If there's an end time, adjust it to maintain duration
        if 'dtend' in exception_event_data:
            original_vevent = event_obj.instance.vevent
            if hasattr(original_vevent, 'dtstart') and hasattr(original_vevent, 'dtend'):
                duration = original_vevent.dtend.value - original_vevent.dtstart.value
                exception_event_data['dtend'] = exception_date + duration

        # Set recurrence-id to link it to the original series
        exception_event_data['recurrence-id'] = exception_date

        # Create the exception event
        exception_ical = _convert_event_params_to_ical(**exception_event_data)
        event_obj.calendar.save_event(exception_ical)

    except (ValueError, AttributeError, TypeError) as err:
        _LOGGER.warning("Failed to create recurring event exception: %s", err)
        # Fallback to updating the entire series
        _update_event_data(event_obj, event_data)


def _update_event_data(event_obj: caldav.CalendarObjectResource, event_data: dict[str, Any]) -> None:
    """Update event data using the best available method."""
    # Try direct parameter update first, fallback to iCalendar string
    try:
        converted_data = _convert_event_params_to_dict(**event_data)
        # Update directly if CalDAV library supports it
        for key, value in converted_data.items():
            setattr(event_obj, key, value)
        event_obj.save()
    except (TypeError, AttributeError):
        # Fallback to iCalendar string replacement
        event_ical = _convert_event_params_to_ical(**event_data)
        event_obj.data = event_ical
        event_obj.save()
