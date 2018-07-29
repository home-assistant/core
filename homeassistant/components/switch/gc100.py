"""
Support for switches using GC100.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.gc100/
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.gc100 import DATA_GC100, CONF_PORTS
from homeassistant.components.switch import (PLATFORM_SCHEMA)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import DEVICE_DEFAULT_NAME

DEPENDENCIES = ['gc100']

_SWITCH_SCHEMA = vol.Schema({
    cv.string: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): vol.All(cv.ensure_list, [_SWITCH_SCHEMA])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the GC100 devices."""
    switches = []
    ports = config.get(CONF_PORTS)
    for port in ports:
        for port_addr, port_name in port.items():
            switches.append(GC100Switch(
                port_name, port_addr, hass.data[DATA_GC100]))
    add_devices(switches, True)


class GC100Switch(ToggleEntity):
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

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._gc100.write_switch(self._port_addr, 1, self.set_state)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._gc100.write_switch(self._port_addr, 0, self.set_state)

    def update(self):
        """Update the sensor state."""
        self._gc100.read_sensor(self._port_addr, self.set_state)

    def set_state(self, state):
        """Set the current state."""
        self._state = state == 1
        self.schedule_update_ha_state()
