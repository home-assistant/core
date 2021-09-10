"""Support for Micropel Coil and Discrete Input sensors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers import config_validation as cv

from . import BINARY_SENSOR_SCHEMA
from .const import CONF_BIT_INDEX, CONF_HUB, CONF_PLC, DOMAIN

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [BINARY_SENSOR_SCHEMA]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Micropel binary sensors."""
    sensors = []

    for sensor in config[CONF_BINARY_SENSORS]:
        hub_name = sensor[CONF_HUB]
        hub = hass.data[DOMAIN][hub_name]
        sensors.append(
            MicropelBinarySensor(
                hub,
                sensor[CONF_UNIQUE_ID],
                sensor[CONF_NAME],
                sensor.get(CONF_PLC),
                sensor[CONF_ADDRESS],
                sensor[CONF_BIT_INDEX],
                sensor.get(CONF_DEVICE_CLASS),
            )
        )

    if not sensors:
        return False
    add_entities(sensors)


class MicropelBinarySensor(BinarySensorEntity):
    """Micropel binary sensor."""

    def __init__(self, hub, unique_id, name, plc, address, bit_index, device_class):
        """Initialize the Micropel binary sensor."""
        self._hub = hub
        self._unique_id = unique_id
        self._name = name
        self._plc = int(plc)
        self._address = int(address)
        self._bit_index = int(bit_index)
        self._device_class = device_class
        self._value = None
        self._available = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return the uuid as the unique_id."""
        return self._unique_id

    def update(self):
        """Update the state of the sensor."""
        try:
            result = self._hub.read_bit(self._plc, self._address, self._bit_index)
            self._value = result
            self._available = True
        except Exception:
            self._available = False
            return
