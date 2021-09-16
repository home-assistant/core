"""This platform allows several binary sensor to be grouped into one binary sensor."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CoreState, Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from . import GroupEntity

DEFAULT_NAME = "Binary Sensor Group"

CONF_ALL = "all"
REG_KEY = f"{BINARY_SENSOR_DOMAIN}_registry"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(BINARY_SENSOR_DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_ALL): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Group Binary Sensor platform."""
    async_add_entities(
        [
            BinarySensorGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config.get(CONF_DEVICE_CLASS),
                config[CONF_ENTITIES],
                config.get(CONF_ALL),
            )
        ]
    )


class BinarySensorGroup(GroupEntity, BinarySensorEntity):
    """Representation of a BinarySensorGroup."""

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        device_class: str | None,
        entity_ids: list[str],
        mode: str | None,
    ) -> None:
        """Initialize a BinarySensorGroup entity."""
        super().__init__()
        self._entity_ids = entity_ids
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self._device_class = device_class
        self._state: str | None = None
        self.mode = any
        if mode:
            self.mode = all

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        async def async_state_changed_listener(event: Event) -> None:
            """Handle child updates."""
            self.async_set_context(event.context)
            await self.async_defer_or_update_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entity_ids, async_state_changed_listener
            )
        )

        if self.hass.state == CoreState.running:
            await self.async_update()
            return

        await super().async_added_to_hass()

    async def async_update(self) -> None:
        """Query all members and determine the binary sensor group state."""
        all_states = [self.hass.states.get(x) for x in self._entity_ids]
        filtered_states: list[str] = [x.state for x in all_states if x is not None]
        self._attr_available = any(
            state != STATE_UNAVAILABLE for state in filtered_states
        )
        if STATE_UNAVAILABLE in filtered_states:
            self._attr_is_on = None
        else:
            states = list(map(lambda x: x == STATE_ON, filtered_states))
            state = self.mode(states)
            self._attr_is_on = state
        self.async_write_ha_state()

    @property
    def device_class(self) -> str | None:
        """Return the sensor class of the binary sensor."""
        return self._device_class
