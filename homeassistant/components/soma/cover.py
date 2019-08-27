"""
Support for Soma Covers.

For more details about this platform, please refer to the documentation at
"""

import logging

from homeassistant.components.cover import CoverDevice, ATTR_POSITION
from homeassistant.components.soma import DOMAIN, SomaEntity, DEVICES, API
from homeassistant.exceptions import PlatformNotReady


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Soma cover platform."""
    def get_covers():
        """Retrieve covers."""
        devices = hass.data[DOMAIN][DEVICES]

        return [SomaCover(cover, hass.data[DOMAIN][API]) for cover in
                devices]

    async_add_entities(await hass.async_add_executor_job(get_covers), True)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old way of setting up platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """
    pass


class SomaCover(SomaEntity, CoverDevice):
    """Representation of a Soma cover device."""

    async def async_update(self):
        """Update the device with the latest data."""
        await super().async_update()

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self.api.close_shade(self.device['mac']) != 'success':
            raise PlatformNotReady()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self.api.open_shade(self.device['mac']) != 'success':
            raise PlatformNotReady()

    def stop_cover(self, **kwargs):
        """Stop the cover."""

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        self.current_position = kwargs[ATTR_POSITION]
        if self.api.set_shade_position(
                self.device['mac'], kwargs[ATTR_POSITION]) != 'success':
            raise PlatformNotReady()

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        return self.current_position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        is_closed = False
        if self.current_position == 100:
            is_closed = True
        return is_closed
