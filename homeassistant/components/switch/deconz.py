"""
Support for deCONZ switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.deconz/
"""
from homeassistant.components.deconz.const import (
    DOMAIN as DATA_DECONZ, DATA_DECONZ_ID, DATA_DECONZ_UNSUB, SWITCH_TYPES)
from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['deconz']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up deCONZ switches."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up switches for deCONZ component.

    Switches are based same device class as lights in deCONZ.
    """
    @callback
    def async_add_switch(lights):
        """Add switch from deCONZ."""
        entities = []
        for light in lights:
            if light.type in SWITCH_TYPES:
                entities.append(DeconzSwitch(light))
        async_add_devices(entities, True)

    hass.data[DATA_DECONZ_UNSUB].append(
        async_dispatcher_connect(hass, 'deconz_new_light', async_add_switch))

    async_add_switch(hass.data[DATA_DECONZ].lights.values())


class DeconzSwitch(SwitchDevice):
    """Representation of a deCONZ switch."""

    def __init__(self, switch):
        """Set up switch and add update callback to get data from websocket."""
        self._switch = switch

    async def async_added_to_hass(self):
        """Subscribe to switches events."""
        self._switch.register_async_callback(self.async_update_callback)
        self.hass.data[DATA_DECONZ_ID][self.entity_id] = self._switch.deconz_id

    @callback
    def async_update_callback(self, reason):
        """Update the switch's state."""
        self.async_schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.state

    @property
    def name(self):
        """Return the name of the switch."""
        return self._switch.name

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return self._switch.uniqueid

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {'on': True}
        await self._switch.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {'on': False}
        await self._switch.async_set_state(data)
