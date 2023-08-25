"""Platform allowing several binary sensor to be grouped into one binary sensor."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import GroupEntity

DEFAULT_NAME = "Binary Sensor Group"

CONF_ALL = "all"
REG_KEY = f"{BINARY_SENSOR_DOMAIN}_registry"

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
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Binary Sensor Group platform."""
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Binary Sensor Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    mode = config_entry.options[CONF_ALL]

    async_add_entities(
        [
            BinarySensorGroup(
                config_entry.entry_id, config_entry.title, None, entities, mode
            )
        ]
    )


@callback
def async_create_preview_binary_sensor(
    name: str, validated_config: dict[str, Any]
) -> BinarySensorGroup:
    """Create a preview sensor."""
    return BinarySensorGroup(
        None,
        name,
        None,
        validated_config[CONF_ENTITIES],
        validated_config[CONF_ALL],
    )


class BinarySensorGroup(GroupEntity, BinarySensorEntity):
    """Representation of a BinarySensorGroup."""

    _attr_available: bool = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        device_class: BinarySensorDeviceClass | None,
        entity_ids: list[str],
        mode: bool | None,
    ) -> None:
        """Initialize a BinarySensorGroup entity."""
        super().__init__()
        self._entity_ids = entity_ids
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id
        self._device_class = device_class
        self.mode = any
        if mode:
            self.mode = all

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the binary sensor group state."""
        states = [
            state.state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)

        valid_state = self.mode(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )
        if not valid_state:
            # Set as unknown if any / all member is not unknown or unavailable
            self._attr_is_on = None
        else:
            # Set as ON if any / all member is ON
            self._attr_is_on = self.mode(state == STATE_ON for state in states)

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the sensor class of the binary sensor."""
        return self._device_class
