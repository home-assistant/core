"""
Support for Soma Covers.

For more details about this platform, please refer to the documentation at
"""

from homeassistant.components.cover import CoverDevice, ATTR_POSITION, \
    ATTR_TILT_POSITION
from homeassistant.components.soma import DOMAIN, SomaEntity, DEVICES, API


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

    def __init__(self, device, api):
        """Initialize the Soma device."""
        super().__init__(device, api)

    async def async_update(self):
        """Update the device with the latest data."""
        await super().async_update()

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.api.close_shade(self.device['mac'])

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.api.open_shade(self.device['mac'])

    def stop_cover(self, **kwargs):
        """Stop the cover."""

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        position = None
        return position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        is_closed = None
        return is_closed

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        orientation = None
        return orientation

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
