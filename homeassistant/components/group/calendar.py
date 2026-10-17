"""Platform allowing several calendar entities to be grouped into one calendar."""

import datetime as dt
from typing import Any, cast, override

import probatio

from homeassistant.components.calendar import (
    CALENDAR_EVENT_SCHEMA,
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    PLATFORM_SCHEMA as CALENDAR_PLATFORM_SCHEMA,
    SERVICE_GET_EVENTS,
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
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
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
        response = cast(
            dict[str, dict[str, list[dict[str, str]]]],
            await hass.services.async_call(
                CALENDAR_DOMAIN,
                SERVICE_GET_EVENTS,
                {
                    ATTR_ENTITY_ID: self._entity_ids,
                    EVENT_START_DATETIME: start_date,
                    EVENT_END_DATETIME: end_date,
                },
                blocking=True,
                context=self._context,
                return_response=True,
            ),
        )
        events = [
            CalendarEvent(**CALENDAR_EVENT_SCHEMA(event))
            for member_response in response.values()
            for event in member_response["events"]
        ]
        return sorted(
            events,
            key=lambda event: (event.start_datetime_local, event.end_datetime_local),
        )

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
