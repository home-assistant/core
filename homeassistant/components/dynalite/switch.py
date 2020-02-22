"""Support for the Dynalite channels and presets as switches."""
from homeassistant.components.switch import SwitchDevice
from homeassistant.core import callback

from .dynalitebase import DynaliteBase, async_setup_entry_base


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""

    @callback
    def switch_from_device(device, bridge):
        return DynaliteSwitch(device, bridge)

    async_setup_entry_base(
        "switch", hass, config_entry, async_add_entities, switch_from_device
    )


class DynaliteSwitch(DynaliteBase, SwitchDevice):
    """Representation of a Dynalite Channel as a Home Assistant Switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._device.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._device.async_turn_off()
