"""Support for Z-Wave switches."""
import time

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveDeviceEntity, workaround


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Switch from Config Entry."""

    @callback
    def async_add_switch(switch):
        """Add Z-Wave Switch."""
        async_add_entities([switch])

    async_dispatcher_connect(hass, "zwave_new_switch", async_add_switch)


def get_device(values, **kwargs):
    """Create zwave entity device."""
    return ZwaveSwitch(values)


class ZwaveSwitch(ZWaveDeviceEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    def __init__(self, values):
        """Initialize the Z-Wave switch device."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.refresh_on_update = (
            workaround.get_device_mapping(values.primary)
            == workaround.WORKAROUND_REFRESH_NODE_ON_UPDATE
        )
        self.last_update = time.perf_counter()
        self._state = self.values.primary.data

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data
        if self.refresh_on_update and time.perf_counter() - self.last_update > 30:
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
