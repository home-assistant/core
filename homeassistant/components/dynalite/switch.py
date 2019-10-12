"""Support for the Dynalite channels and presets as switches."""
from .dynalitebase import async_setup_channel_entry, DynaliteBase
from homeassistant.components.switch import SwitchDevice


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""
    async_setup_channel_entry("switch", hass, config_entry, async_add_entities)


class DynaliteSwitch(DynaliteBase, SwitchDevice):
    """Representation of a Dynalite Channel as a Home Assistant Switch."""

    def __init__(self, device, bridge):
        """Initialize the switch."""
        super().__init__(device, bridge)

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
