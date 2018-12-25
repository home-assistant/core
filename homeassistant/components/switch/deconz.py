"""
Support for deCONZ switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.deconz/
"""
from homeassistant.components.deconz.const import (
    DECONZ_REACHABLE, DOMAIN as DECONZ_DOMAIN, POWER_PLUGS, SIRENS)
from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['deconz']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up deCONZ switches."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for deCONZ component.

    Switches are based same device class as lights in deCONZ.
    """
    gateway = hass.data[DECONZ_DOMAIN]

    @callback
    def async_add_switch(lights):
        """Add switch from deCONZ."""
        entities = []
        for light in lights:
            if light.type in POWER_PLUGS:
                entities.append(DeconzPowerPlug(light, gateway))
            elif light.type in SIRENS:
                entities.append(DeconzSiren(light, gateway))
        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(hass, 'deconz_new_light', async_add_switch))

    async_add_switch(gateway.api.lights.values())


class DeconzSwitch(SwitchDevice):
    """Representation of a deCONZ switch."""

    def __init__(self, switch, gateway):
        """Set up switch and add update callback to get data from websocket."""
        self._switch = switch
        self.gateway = gateway
        self.unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Subscribe to switches events."""
        self._switch.register_async_callback(self.async_update_callback)
        self.gateway.deconz_ids[self.entity_id] = self._switch.deconz_id
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, DECONZ_REACHABLE, self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect switch object when removed."""
        if self.unsub_dispatcher is not None:
            self.unsub_dispatcher()
        self._switch.remove_callback(self.async_update_callback)
        self._switch = None

    @callback
    def async_update_callback(self, reason):
        """Update the switch's state."""
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._switch.name

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return self._switch.uniqueid

    @property
    def available(self):
        """Return True if light is available."""
        return self.gateway.available and self._switch.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if (self._switch.uniqueid is None or
                self._switch.uniqueid.count(':') != 7):
            return None
        serial = self._switch.uniqueid.split('-', 1)[0]
        bridgeid = self.gateway.api.config.bridgeid
        return {
            'connections': {(CONNECTION_ZIGBEE, serial)},
            'identifiers': {(DECONZ_DOMAIN, serial)},
            'manufacturer': self._switch.manufacturer,
            'model': self._switch.modelid,
            'name': self._switch.name,
            'sw_version': self._switch.swversion,
            'via_hub': (DECONZ_DOMAIN, bridgeid),
        }


class DeconzPowerPlug(DeconzSwitch):
    """Representation of power plugs from deCONZ."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.state

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {'on': True}
        await self._switch.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {'on': False}
        await self._switch.async_set_state(data)


class DeconzSiren(DeconzSwitch):
    """Representation of sirens from deCONZ."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._switch.alert == 'lselect'

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {'alert': 'lselect'}
        await self._switch.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {'alert': 'none'}
        await self._switch.async_set_state(data)
