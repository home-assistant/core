"""Support for creating a sensor based on a attribute value."""
from __future__ import annotations

from datetime import datetime
import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:database-arrow-up"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_ATTRIBUTE): cv.string,
        vol.Required(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Required(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize attribute sensor config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )
    attribute: str = config_entry.options[CONF_ATTRIBUTE]
    device_class: SensorDeviceClass = config_entry.options[CONF_DEVICE_CLASS]
    unit_of_measurement: str = config_entry.options[CONF_UNIT_OF_MEASUREMENT]

    async_add_entities(
        [
            AttributeSensor(
                entity_id,
                config_entry.title,
                attribute,
                device_class,
                unit_of_measurement,
                config_entry.entry_id,
            )
        ]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the min/max/mean sensor."""
    entity_id: str = config[CONF_ENTITY_ID]
    name: str | None = config.get(CONF_NAME)
    attribute: str = config[CONF_ATTRIBUTE]
    device_class: SensorDeviceClass = config[CONF_DEVICE_CLASS]
    unit_of_measurement: str = config[CONF_UNIT_OF_MEASUREMENT]
    unique_id = config.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            AttributeSensor(
                entity_id, name, attribute, device_class, unit_of_measurement, unique_id
            )
        ]
    )


class AttributeSensor(SensorEntity):
    """Representation of a attribute sensor."""

    _attr_icon = ICON
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entity_id: str,
        name: str | None,
        attribute: str,
        device_class: SensorDeviceClass,
        unit_of_measurement: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the attribute sensor."""
        self._attr_unique_id = unique_id
        self._entity_id = entity_id
        self._attribute = attribute
        self._attr_device_class = device_class.value
        self._attr_native_unit_of_measurement = unit_of_measurement

        if name:
            self._attr_name = name
        else:
            self._attr_name = f"{attribute} sensor".capitalize()

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        value: StateType | datetime = 4
        return value
