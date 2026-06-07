"""Platform allowing several event entities to be grouped into one event."""

import itertools
from typing import Any

import voluptuous as vol

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    DOMAIN as EVENT_DOMAIN,
    PLATFORM_SCHEMA as EVENT_PLATFORM_SCHEMA,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.target import TargetStateChangedData
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

DEFAULT_NAME = "Event group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = EVENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(EVENT_DOMAIN),
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
    entities = {"entity_id": config[CONF_ENTITIES]}
    async_add_entities(
        [
            EventGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                entities,
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize event group config entry."""
    target_config = dict(config_entry.options[CONF_ENTITIES])
    entity_ids = target_config.get("entity_id", [])
    if entity_ids:
        registry = er.async_get(hass)
        entities = er.async_validate_entity_ids(registry, entity_ids)
        target_config["entity_id"] = entities
    async_add_entities(
        [
            EventGroup(
                config_entry.entry_id,
                config_entry.title,
                target_config,
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
        target_config: dict[str, Any],
    ) -> None:
        """Initialize an event group."""
        super().__init__()
        self._target_config = target_config
        self._domain = EVENT_DOMAIN
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_event_types = []

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def async_state_changed_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Handle child updates."""
            if not self.hass.is_running:
                return

            self.async_set_context(target_state_change_data.state_change_event.context)

            # Update all properties of the group
            self.async_update_group_state()

            # Re-fire if one of the members fires an event, but only
            # if the original state was not unavailable or unknown.
            if (
                (
                    old_state := target_state_change_data.state_change_event.data[
                        "old_state"
                    ]
                )
                and old_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                and (
                    new_state := target_state_change_data.state_change_event.data[
                        "new_state"
                    ]
                )
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
