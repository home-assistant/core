"""Support for WebDav Calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import Any

import caldav
from ical.types import Range
from icalendar import vDDDTypes, vRecur
import voluptuous as vol

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    EVENT_END,
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
            name = f"{username.capitalize() + ' ' if username else ''}{calendar.name}"  # default entity name is USERNAME calendar.name so the user can better distinguish between calendars.
            device_id = f"{username} {calendar.name}"
            entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT,
                f"{url + ' ' if url else ''}{username + ' ' if username else ''}{calendar.name}",  # entity_id based on URL, USERNAME and calendarname to identify a calendar uniquely
                hass=hass,
            )
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

        return await self.hass.async_add_executor_job(save_event)

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

    async def async_update_event(  # noqa: C901
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Update an existing event on the calendar.

        Supports updating
        - a single event,
        - a recurring event,
        - a single occurrence of a recurring event (in that case, the RRULE can not be changed),
        - an ocurrrence and all future occurrences of a recurring event (here, the RRULE may differ).

        In the last case, we try to mimic the behavior of Nextcloud and split the series in two recurring events:
        - the original recurring event is modified to end just before the updated occurrence.
        - a new recurring event is created in place of the occurrence to be updated.
        """

        _LOGGER.debug(
            "async_update_event called with uid=%s, recurrence_id=%s and recurrence_range=%s",
            uid,
            recurrence_id,
            recurrence_range,
        )

        # Home Assistant currently supports only THIS_AND_FUTURE.
        # For updating, we support only updating the entire series or a single occurrence.
        # If THIS_AND_FUTURE is specified, we update the master event (which updates the entire series), no matter which recurrence_id is specified.
        if recurrence_range == Range.THIS_AND_FUTURE:
            # Get the master event of the series by uid
            master_event = await self.coordinator.async_get_event(self.hass, uid)
            if not master_event:
                _LOGGER.error("Event with uid %s not found", uid)
                return

            # Validate recurrence_id is provided
            if not recurrence_id:
                _LOGGER.error(
                    "The recurrence_id must be provided when recurrence_range is THIS_AND_FUTURE"
                )
                return

            assert hasattr(master_event, "icalendar_component")  # for mypy
            assert hasattr(master_event.vobject_instance, "vevent")  # for mypy

            # Parse recurrence_id
            recurrence_datetime = self.coordinator.to_local(
                self.coordinator.parse_recurrence_id(recurrence_id)
            )

            # Get the start date of the master event
            start_master = self.coordinator.to_datetime(
                master_event.icalendar_component[EVENT_START].dt
            )

            # If the recurrence_datetime is after the start of the master event,
            # we need to split the series in two by updating the RRULE of the master event
            # to set the UNTIL attribute to before the recurrence_datetime and
            # create a new recurrence for the specified recurrence_id with the updated attributes.
            if recurrence_datetime > start_master:
                _LOGGER.debug(
                    "The recurrence_id %s is after the start of the master event %s. Original series will be updated to end before the recurrence_id and a new recurring event will be created in place of the new event",
                    recurrence_datetime,
                    start_master,
                )
                # Remove COUNT from master_event's RRULE if present
                # and set UNTIL to the day before the recurrence_datetime
                master_event.icalendar_component[EVENT_RRULE].pop(
                    "count", None
                )  # use pop to avoid KeyError
                until = recurrence_datetime - timedelta(days=1)
                master_event.icalendar_component[EVENT_RRULE]["until"] = until

                # Create a new event in the calendar and retrieve its uid
                new_event = await self._async_create_event(**event)
                if not isinstance(new_event, caldav.Event):
                    _LOGGER.error(
                        "Failed to create new event in calendar while updating event with uid=%s and recurrence_id=%s",
                        uid,
                        recurrence_id,
                    )
                    return

                assert hasattr(new_event, "icalendar_component")  # for mypy

                # Get the uid of the newly created event
                new_event_uid = new_event.icalendar_component["uid"]

                # Link the new event to the master event as a sibling
                # Note: set_relation will save the event automatically,
                # so no need to call new_event.save() afterwards
                # But we need to use async_add_executor_job here because set_relation
                # is not async and we don't want to block the event loop
                def update_event_relations(
                    this: caldav.CalendarObjectResource,
                    that: caldav.CalendarObjectResource,
                ) -> None:
                    this.set_relation(that, reltype="SIBLING", set_reverse=True)  # type: ignore[attr-defined]

                # Add relation between master event and new event.
                # Note: this will also save the changes to the master_event's RRULE.
                await self.hass.async_add_executor_job(
                    update_event_relations, new_event, master_event
                )

                # If the master event has related-to links, we need to update those events as well
                if hasattr(master_event.vobject_instance.vevent, "related-to"):
                    # UIDs of related events
                    related_uids = master_event.icalendar_component["related-to"]
                    missing_uids = []
                    for related_uid in related_uids:
                        if related_uid == new_event_uid:
                            continue

                        # Get related event from server
                        related_event = await self.coordinator.async_get_event(
                            self.hass, related_uid
                        )

                        # It might seem that when an event is deleted, the related-to links in the other events are not (reliably? at all?) updated.
                        # Todo1: check if this is a bug in nextcloud or in the caldav library.
                        # Todo2: provide an option to clean up related-to links that point to non-existing events.
                        # For now, we just log a message and skip the missing event.
                        if not related_event:
                            _LOGGER.info(
                                "Event with uid=%s could not be found while searching for related events of event with uid=%s",
                                related_uid,
                                master_event.icalendar_component["uid"],
                            )
                            missing_uids.append(related_uid)
                            continue

                        await self.hass.async_add_executor_job(
                            update_event_relations, new_event, related_event
                        )

                # Reminder: no need to save the new_event, it was already saved by set_relation

            else:
                # Update all attributes of the master event with the values from the event dict
                for a, v in event.items():
                    if a in (EVENT_START, EVENT_END):
                        master_event.icalendar_component[a] = vDDDTypes(
                            self.coordinator.to_local(v)
                        )
                    elif a == EVENT_RRULE:
                        master_event.icalendar_component[a] = vRecur.from_ical(v)
                    else:
                        master_event.icalendar_component[a] = v

                # If the RRULE is empty, remove it from the event to make it a non-recurring event
                if EVENT_RRULE not in event:
                    master_event.icalendar_component.pop(EVENT_RRULE, None)

                def update_event() -> None:
                    master_event.save()

                # Update the master event, which will update the entire series
                await self.hass.async_add_executor_job(update_event)

        elif recurrence_id is not None:
            # Update only the specified occurrence of the series
            recurrence = await self.coordinator.async_get_event_recurrence(
                self.hass, uid, recurrence_id
            )

            if not recurrence:
                _LOGGER.error(
                    "Recurrence with uid %s and recurrence_id %s not found",
                    uid,
                    recurrence_id,
                )
                return

            assert hasattr(recurrence, "icalendar_component")  # for mypy

            # Update all attributes of the event with the values from the event dict
            for a, v in event.items():
                if a in (EVENT_START, EVENT_END):
                    recurrence.icalendar_component[a] = vDDDTypes(
                        self.coordinator.to_local(v)
                    )
                elif a == EVENT_RRULE:
                    # RRULE cannot be updated for a single occurrence
                    # Normally, it is expected that Home Assistant takes car of this
                    # and does not try to update the RRULE of a single occurrence.
                    _LOGGER.warning(
                        "RRULE cannot be updated for a single occurrence. Ignoring RRULE update for event with uid=%s and recurrence_id=%s",
                        uid,
                        recurrence_id,
                    )
                else:
                    recurrence.icalendar_component[a] = v

            def update_event() -> None:
                recurrence.save()

            # Save changes to the event
            await self.hass.async_add_executor_job(update_event)

        else:
            # Update a non-recurring event by uid
            non_recurring_event = await self.coordinator.async_get_event(self.hass, uid)

            if not non_recurring_event:
                _LOGGER.error("Event with uid %s not found", uid)
                return

            assert hasattr(non_recurring_event, "icalendar_component")  # for mypy

            # Update all attributes of the event with the values from the event dict
            for a, v in event.items():
                if a in (EVENT_START, EVENT_END):
                    non_recurring_event.icalendar_component[a] = vDDDTypes(
                        self.coordinator.to_local(v)
                    )
                elif a == EVENT_RRULE:
                    non_recurring_event.icalendar_component[a] = vRecur.from_ical(v)
                else:
                    non_recurring_event.icalendar_component[a] = v

            def update_event() -> None:
                non_recurring_event.save()

            # Save changes to the event
            await self.hass.async_add_executor_job(update_event)

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
