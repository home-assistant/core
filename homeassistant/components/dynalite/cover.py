"""Support for the Dynalite channels as covers."""
from homeassistant.components.cover import CoverDevice
from homeassistant.core import callback

from .dynalitebase import DynaliteBase, async_setup_entry_base


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Record the async_add_entities function to add them later when received from Dynalite."""

    @callback
    def cover_from_device(device, bridge):
        if device.has_tilt:
            return DynaliteCoverWithTilt(device, bridge)
        return DynaliteCover(device, bridge)

    async_setup_entry_base(
        "cover", hass, config_entry, async_add_entities, cover_from_device
    )


class DynaliteCover(DynaliteBase, CoverDevice):
    """Representation of a Dynalite Channel as a Home Assistant Cover."""

    @property
    def device_class(self):
        """Return the class of the device."""
        return self._device.device_class

    @property
    def current_cover_position(self):
        """Return the position of the cover from 0 to 100."""
        return self._device.current_cover_position

    @property
    def is_opening(self):
        """Return true if cover is opening."""
        return self._device.is_opening

    @property
    def is_closing(self):
        """Return true if cover is closing."""
        return self._device.is_closing

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._device.is_closed

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._device.async_open_cover(**kwargs)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._device.async_close_cover(**kwargs)

    async def async_set_cover_position(self, **kwargs):
        """Set the cover position."""
        await self._device.async_set_cover_position(**kwargs)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._device.async_stop_cover(**kwargs)


class DynaliteCoverWithTilt(DynaliteCover):
    """Representation of a Dynalite Channel as a Home Assistant Cover that uses up and down for tilt."""

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt position."""
        return self._device.current_cover_tilt_position

    async def async_open_cover_tilt(self, **kwargs):
        """Open cover tilt."""
        await self._device.async_open_cover_tilt(**kwargs)

    async def async_close_cover_tilt(self, **kwargs):
        """Close cover tilt."""
        await self._device.async_close_cover_tilt(**kwargs)

    async def async_set_cover_tilt_position(self, **kwargs):
        """Set the cover tilt position."""
        await self._device.async_set_cover_tilt_position(**kwargs)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
        await self._device.async_stop_cover_tilt(**kwargs)
