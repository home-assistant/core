"""Representation of Z-Wave switches."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave switch from config entry."""

    @callback
    def async_add_switch(value):
        """Add Z-Wave Switch."""
        switch = ZWaveSwitch(value)

        async_add_entities([switch])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, "zwave_new_switch", async_add_switch)
    )

    await hass.data[DOMAIN][config_entry.entry_id]["mark_platform_loaded"]("switch")


class ZWaveSwitch(ZWaveDeviceEntity, SwitchEntity):
    """Representation of a Z-Wave switch."""

    @property
    def state(self):
        """Return the state of the switch."""
        if self.values.primary.value:
            return STATE_ON
        return STATE_OFF

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.values.primary.send_value(True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.values.primary.send_value(False)
