"""Support for Dynalite channels as lights."""
from .dynalitebase import async_setup_channel_entry, DynaliteBase

from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""
    async_setup_channel_entry("light", hass, config_entry, async_add_entities)


class DynaliteLight(DynaliteBase, Light):
    """Representation of a Dynalite Channel as a Home Assistant Light."""

    def __init__(self, device, bridge):
        """Initialize the light."""
        super().__init__(device, bridge)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._device.brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        await self._device.async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._device.async_turn_off(**kwargs)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS
