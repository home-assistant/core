"""Support for switches using GC100."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_PORTS, DATA_GC100

_SWITCH_SCHEMA = vol.Schema({cv.string: cv.string})

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_PORTS): vol.All(cv.ensure_list, [_SWITCH_SCHEMA])}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GC100 devices."""
    switches = []
    ports = config[CONF_PORTS]
    for port in ports:
        for port_addr, port_name in port.items():
            switches.append(GC100Switch(port_name, port_addr, hass.data[DATA_GC100]))
    add_entities(switches, True)


class GC100Switch(SwitchEntity):
    """Represent a switch/relay from GC100."""

    def __init__(self, name, port_addr, gc100):
        """Initialize the GC100 switch."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port_addr = port_addr
        self._gc100 = gc100
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._gc100.write_switch(self._port_addr, 1, self.set_state)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._gc100.write_switch(self._port_addr, 0, self.set_state)

    def update(self) -> None:
        """Update the sensor state."""
        self._gc100.read_sensor(self._port_addr, self.set_state)

    def set_state(self, state):
        """Set the current state."""
        self._state = state == 1
        self.schedule_update_ha_state()
