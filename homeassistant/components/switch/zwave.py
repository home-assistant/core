"""
Z-Wave platform that handles simple binary switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.zwave/
"""
import logging
import time
from homeassistant.core import callback
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components import zwave
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old method of setting up Z-Wave switches."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Switch from Config Entry."""
    @callback
    def async_add_switch(switch):
        """Add Z-Wave Switch."""
        async_add_entities([switch])

    async_dispatcher_connect(hass, 'zwave_new_switch', async_add_switch)


def get_device(values, **kwargs):
    """Create zwave entity device."""
    return ZwaveSwitch(values)


class ZwaveSwitch(zwave.ZWaveDeviceEntity, SwitchDevice):
    """Representation of a Z-Wave switch."""

    def __init__(self, values):
        """Initialize the Z-Wave switch device."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.refresh_on_update = (
            zwave.workaround.get_device_mapping(values.primary) ==
            zwave.workaround.WORKAROUND_REFRESH_NODE_ON_UPDATE)
        self.last_update = time.perf_counter()
        self._state = self.values.primary.data

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data
        if self.refresh_on_update and \
                time.perf_counter() - self.last_update > 30:
            self.last_update = time.perf_counter()
            self.node.request_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.node.set_switch(self.values.primary.value_id, True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.node.set_switch(self.values.primary.value_id, False)
