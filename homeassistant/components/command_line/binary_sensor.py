"""Support for custom shell commands to retrieve values."""
from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT
from .sensor import CommandSensorData

DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"

SCAN_INTERVAL = timedelta(seconds=60)

BINARY_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BINARY_SENSOR_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Command line Binary Sensor."""
    if discovery_info is None:
        entities = [config]
    else:
        entities = discovery_info["entities"]

    binary_sensors = []

    for entity in entities:
        command = entity.get(CONF_COMMAND)
        command_timeout = entity.get(CONF_COMMAND_TIMEOUT)
        value_template = entity.get(CONF_VALUE_TEMPLATE)
        if value_template is not None:
            value_template.hass = hass

        binary_sensors.append(
            CommandBinarySensor(
                hass,
                CommandSensorData(hass, command, command_timeout),
                entity.get(CONF_NAME),
                entity.get(CONF_DEVICE_CLASS),
                entity.get(CONF_PAYLOAD_ON),
                entity.get(CONF_PAYLOAD_OFF),
                value_template,
                entity.get(CONF_UNIQUE_ID),
            )
        )

    add_entities(binary_sensors, True)


class CommandBinarySensor(BinarySensorEntity):
    """Representation of a command line binary sensor."""

    def __init__(
        self,
        hass,
        data,
        name,
        device_class,
        payload_on,
        payload_off,
        value_template,
        unique_id,
    ):
        """Initialize the Command line binary sensor."""
        self._hass = hass
        self.data = data
        self._name = name
        self._device_class = device_class
        self._state = False
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._value_template = value_template
        self._attr_unique_id = unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    def update(self):
        """Get the latest data and updates the state."""
        self.data.update()
        value = self.data.value

        if self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(value, False)
        if value == self._payload_on:
            self._state = True
        elif value == self._payload_off:
            self._state = False
