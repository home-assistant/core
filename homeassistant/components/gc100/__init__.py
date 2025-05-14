"""Support for controlling Global Cache gc100."""

from __future__ import annotations

import gc100
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

CONF_PORTS = "ports"

DEFAULT_PORT = 4998
DOMAIN = "gc100"

DATA_GC100: HassKey[GC100Device] = HassKey("gc100")

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up the gc100 component."""
    config = base_config[DOMAIN]
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    gc_device = gc100.GC100SocketClient(host, port)

    def cleanup_gc100(event):
        """Stuff to do before stopping."""
        gc_device.quit()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gc100)

    hass.data[DATA_GC100] = GC100Device(hass, gc_device)

    return True


class GC100Device:
    """The GC100 component."""

    def __init__(self, hass, gc_device):
        """Init a gc100 device."""
        self.hass = hass
        self.gc_device = gc_device

    def read_sensor(self, port_addr, callback):
        """Read a value from a digital input."""
        self.gc_device.read_sensor(port_addr, callback)

    def write_switch(self, port_addr, state, callback):
        """Write a value to a relay."""
        self.gc_device.write_switch(port_addr, state, callback)

    def subscribe(self, port_addr, callback):
        """Add detection for RISING and FALLING events."""
        self.gc_device.subscribe_notify(port_addr, callback)
