"""Platform allowing several calendar entities to be grouped into one calendar."""

import asyncio
import datetime as dt
from typing import Any, override

import probatio

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    PLATFORM_SCHEMA as CALENDAR_PLATFORM_SCHEMA,
    CalendarEntity,
    CalendarEntityStateAttribute,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
)
from homeassistant.core import (
    Event,
    EventStateReportedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_state_report_event
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

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


def _event_from_state(state: State) -> CalendarEvent | None:
    """Rebuild the current or next event of a member from its state attributes."""
    attributes = state.attributes
    if (summary := attributes.get(CalendarEntityStateAttribute.MESSAGE)) is None:
        return None

    timezone = dt_util.get_default_time_zone()
    start = dt.datetime.strptime(
        attributes[CalendarEntityStateAttribute.START_TIME], DATE_STR_FORMAT
    ).replace(tzinfo=timezone)
    end = dt.datetime.strptime(
        attributes[CalendarEntityStateAttribute.END_TIME], DATE_STR_FORMAT
    ).replace(tzinfo=timezone)
    return CalendarEvent(
        start=start.date()
        if attributes[CalendarEntityStateAttribute.ALL_DAY]
        else start,
        end=end.date() if attributes[CalendarEntityStateAttribute.ALL_DAY] else end,
        summary=summary,
        description=attributes.get(CalendarEntityStateAttribute.DESCRIPTION) or None,
        location=attributes.get(CalendarEntityStateAttribute.LOCATION) or None,
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
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self._member_events: list[CalendarEvent] = []

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        @callback
        def async_member_reported(_: Event[EventStateReportedData]) -> None:
            """Refresh event subscribers when a member rewrites an unchanged state."""
            self.async_update_event_listeners()

        self.async_on_remove(
            async_track_state_report_event(
                self.hass, self._entity_ids, async_member_reported
            )
        )

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event of all members."""
        now = dt_util.now()
        return min(
            (event for event in self._member_events if event.end_datetime_local > now),
            key=lambda event: (event.start_datetime_local, event.end_datetime_local),
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
        # Members are queried directly: calling the get_events action would
        # make polling members refresh and write their state on every fetch.
        component: EntityComponent[CalendarEntity] = hass.data[CALENDAR_DOMAIN]
        calendars = self.async_member_calendars(component, {self.entity_id})
        member_events = await asyncio.gather(
            *(
                calendar.async_get_events(hass, start_date, end_date)
                for calendar in calendars
            )
        )
        events = [event for events in member_events for event in events]
        return sorted(
            events,
            key=lambda event: (event.start_datetime_local, event.end_datetime_local),
        )

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
            if (entity := component.get_entity(entity_id)) is None or not (
                entity.available
            ):
                continue
            if isinstance(entity, CalendarGroup):
                calendars.extend(entity.async_member_calendars(component, visited))
            else:
                calendars.append(entity)
        return calendars

    @callback
    @override
    def async_update_group_state(self) -> None:
        """Query all members and determine the calendar group state."""
        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        self._member_events = [
            event
            for state in states
            if state.state != STATE_UNAVAILABLE
            and (event := _event_from_state(state)) is not None
        ]

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)
