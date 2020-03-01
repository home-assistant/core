"""Support for Dynalite channels as lights."""
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light
from homeassistant.core import callback

from .dynalitebase import DynaliteBase, async_setup_entry_base


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""

    @callback
    def light_from_device(device, bridge):
        return DynaliteLight(device, bridge)

    async_setup_entry_base(
        hass, config_entry, async_add_entities, "light", light_from_device
    )


class DynaliteLight(DynaliteBase, Light):
    """Representation of a Dynalite Channel as a Home Assistant Light."""

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
