"""Support for deCONZ switches."""
from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_LIGHT, POWER_PLUGS, SIRENS
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for deCONZ component.

    Switches are based on the same device class as lights in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_switch(lights):
        """Add switch from deCONZ."""
        entities = []

        for light in lights:

            if (
                light.type in POWER_PLUGS
                and light.uniqueid not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzPowerPlug(light, gateway))

            elif (
                light.type in SIRENS and light.uniqueid not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzSiren(light, gateway))

        if entities:
            async_add_entities(entities)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_LIGHT), async_add_switch
        )
    )

    async_add_switch(gateway.api.lights.values())


class DeconzPowerPlug(DeconzDevice, SwitchEntity):
    """Representation of a deCONZ power plug."""

    TYPE = DOMAIN

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.state

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {"on": True}
        await self._device.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {"on": False}
        await self._device.async_set_state(data)


class DeconzSiren(DeconzDevice, SwitchEntity):
    """Representation of a deCONZ siren."""

    TYPE = DOMAIN

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.alert == "lselect"

    async def async_turn_on(self, **kwargs):
        """Turn on switch."""
        data = {"alert": "lselect"}
        await self._device.async_set_state(data)

    async def async_turn_off(self, **kwargs):
        """Turn off switch."""
        data = {"alert": "none"}
        await self._device.async_set_state(data)
