"""Platform allowing several event entities to be grouped into one event."""
from __future__ import annotations

import itertools
from typing import Any

import voluptuous as vol

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    DOMAIN,
    PLATFORM_SCHEMA,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType

from . import GroupEntity

DEFAULT_NAME = "Event group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    _: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    __: DiscoveryInfoType | None = None,
) -> None:
    """Set up the event group platform."""
    async_add_entities(
        [
            EventGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize event group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            EventGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
            )
        ]
    )


@callback
def async_create_preview_event(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> EventGroup:
    """Create a preview sensor."""
    return EventGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class EventGroup(GroupEntity, EventEntity):
    """Representation of an event group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
    ) -> None:
        """Initialize an event group."""
        self._entity_ids = entity_ids
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self._attr_event_types = []

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(
            event: EventType[EventStateChangedData],
        ) -> None:
            """Handle child updates."""
            if not self.hass.is_running:
                return

            self.async_set_context(event.context)

            # Update all properties of the group
            self.async_update_group_state()

            # Re-fire if one of the members fires an event, but only
            # if the original state was not unavailable or unknown.
            if (
                (old_state := event.data["old_state"])
                and old_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                and (new_state := event.data["new_state"])
                and new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                and (event_type := new_state.attributes.get(ATTR_EVENT_TYPE))
            ):
                event_attributes = new_state.attributes.copy()

                # We should not propagate the event properties as
                # fired event attributes.
                del event_attributes[ATTR_EVENT_TYPE]
                del event_attributes[ATTR_EVENT_TYPES]
                event_attributes.pop(ATTR_DEVICE_CLASS, None)
                event_attributes.pop(ATTR_FRIENDLY_NAME, None)

                # Fire the group event
                self._trigger_event(event_type, event_attributes)

            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, async_state_changed_listener
            )
        )

        await super().async_added_to_hass()

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the event group properties."""
        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        # None of the members are available
        if not states:
            self._attr_available = False
            return

        # Gather and combine all possible event types from all entities
        self._attr_event_types = list(
            set(
                itertools.chain.from_iterable(
                    state.attributes.get(ATTR_EVENT_TYPES, []) for state in states
                )
            )
        )

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)
