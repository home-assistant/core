"""Support for binary sensor using GC100."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_PORTS, DATA_GC100

_SENSORS_SCHEMA = vol.Schema({cv.string: cv.string})

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PORTS): vol.All(cv.ensure_list, [_SENSORS_SCHEMA])}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GC100 devices."""
    binary_sensors = []
    ports = config[CONF_PORTS]
    for port in ports:
        for port_addr, port_name in port.items():
            binary_sensors.append(
                GC100BinarySensor(port_name, port_addr, hass.data[DATA_GC100])
            )
    add_entities(binary_sensors, True)


class GC100BinarySensor(BinarySensorEntity):
    """Representation of a binary sensor from GC100."""

    def __init__(self, name, port_addr, gc100):
        """Initialize the GC100 binary sensor."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port_addr = port_addr
        self._gc100 = gc100
        self._state = None

        # Subscribe to be notified about state changes (PUSH)
        self._gc100.subscribe(self._port_addr, self.set_state)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state

    def update(self) -> None:
        """Update the sensor state."""
        self._gc100.read_sensor(self._port_addr, self.set_state)

    def set_state(self, state):
        """Set the current state."""
        self._state = state == 1
        self.schedule_update_ha_state()
