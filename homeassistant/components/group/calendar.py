"""Platform allowing several calendar entities to be grouped into one calendar."""

import asyncio
import datetime as dt
from typing import Any, override

import probatio

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    PLATFORM_SCHEMA as CALENDAR_PLATFORM_SCHEMA,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITIES, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import Event, EventStateReportedData, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_state_report_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from .const import GroupEntityStateAttribute
from .entity import GroupEntity

DEFAULT_NAME = "Calendar group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = CALENDAR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ENTITIES): cv.entities_domain(CALENDAR_DOMAIN),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    _: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    __: DiscoveryInfoType | None = None,
) -> None:
    """Set up the calendar group platform."""
    async_add_entities(
        [
            CalendarGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize calendar group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            CalendarGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
            )
        ]
    )


@callback
def async_create_preview_calendar(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> CalendarGroup:
    """Create a preview calendar."""
    return CalendarGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


def _event_sort_key(event: CalendarEvent) -> tuple[dt.datetime, dt.datetime]:
    """Order events chronologically.

    Uses UTC, as comparing local times ignores the DST fold.
    """
    return (
        dt_util.as_utc(event.start_datetime_local),
        dt_util.as_utc(event.end_datetime_local),
    )


class CalendarGroup(GroupEntity, CalendarEntity):
    """Representation of a calendar group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
    ) -> None:
        """Initialize a calendar group."""
        self._entity_ids = entity_ids
        self._attr_name = name
        self._attr_extra_state_attributes = {
            GroupEntityStateAttribute.ENTITY_ID: entity_ids
        }
        self._attr_unique_id = unique_id
        self._member_events: list[CalendarEvent] = []

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        @callback
        def async_member_reported(_: Event[EventStateReportedData]) -> None:
            """Refresh member events when a member rewrites an unchanged state."""
            # A nested group reports an unchanged state when only its later
            # events change. Writing state here could loop through cycles.
            self.async_update_group_state()
            if self._event_listener_debouncer:
                self._event_listener_debouncer.async_schedule_call()

        self.async_on_remove(
            async_track_state_report_event(
                self.hass, self._entity_ids, async_member_reported
            )
        )

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event of all members."""
        now = dt_util.utcnow()
        return min(
            (
                event
                for event in self._member_events
                if dt_util.as_utc(event.end_datetime_local) > now
            ),
            key=_event_sort_key,
            default=None,
        )

    @override
    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events of all members within a datetime range."""
        member_events = await asyncio.gather(
            *(
                calendar.async_get_events(hass, start_date, end_date)
                for calendar in self._async_calendars()
            )
        )
        events = [event for events in member_events for event in events]
        return sorted(events, key=_event_sort_key)

    @callback
    def _async_calendars(self) -> list[CalendarEntity]:
        """Return the available member calendars."""
        # Members are used directly: the get_events action would make polling
        # members refresh on every fetch, and their state attributes lose the
        # event's UTC offset.
        component: EntityComponent[CalendarEntity] | None = self.hass.data.get(
            CALENDAR_DOMAIN
        )
        if component is None:
            return []
        return self.async_member_calendars(component, {self.entity_id})

    @callback
    def async_member_calendars(
        self, component: EntityComponent[CalendarEntity], visited: set[str]
    ) -> list[CalendarEntity]:
        """Return the available member calendars, expanding nested groups.

        Each calendar is returned once, which also breaks membership cycles.
        """
        calendars: list[CalendarEntity] = []
        for entity_id in self._entity_ids:
            if entity_id in visited:
                continue
            visited.add(entity_id)
            if (entity := component.get_entity(entity_id)) is None:
                continue
            if isinstance(entity, CalendarGroup):
                calendars.extend(entity.async_member_calendars(component, visited))
            elif entity.available:
                calendars.append(entity)
        return calendars

    @callback
    @override
    def async_update_group_state(self) -> None:
        """Query all members and determine the calendar group state."""
        calendars = self._async_calendars()
        self._member_events = [
            event for calendar in calendars if (event := calendar.event) is not None
        ]

        # Set group as unavailable if no member calendar is available
        self._attr_available = bool(calendars)
