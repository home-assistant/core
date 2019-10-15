"""
Support for Somfy Covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.somfy/
"""

from homeassistant.components.cover import (
    CoverDevice,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.components.somfy import DOMAIN, SomfyEntity, DEVICES, API


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy cover platform."""

    def get_covers():
        """Retrieve covers."""
        from pymfy.api.devices.category import Category

        categories = {
            Category.ROLLER_SHUTTER.value,
            Category.INTERIOR_BLIND.value,
            Category.EXTERIOR_BLIND.value,
        }

        devices = hass.data[DOMAIN][DEVICES]

        return [
            SomfyCover(cover, hass.data[DOMAIN][API])
            for cover in devices
            if categories & set(cover.categories)
        ]

    async_add_entities(await hass.async_add_executor_job(get_covers), True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """
    pass


class SomfyCover(SomfyEntity, CoverDevice):
    """Representation of a Somfy cover device."""

    def __init__(self, device, api):
        """Initialize the Somfy device."""
        from pymfy.api.devices.blind import Blind

        super().__init__(device, api)
        self.cover = Blind(self.device, self.api)

    async def async_update(self):
        """Update the device with the latest data."""
        from pymfy.api.devices.blind import Blind

        await super().async_update()
        self.cover = Blind(self.device, self.api)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self.cover.close()

    def open_cover(self, **kwargs):
        """Open the cover."""
        self.cover.open()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.cover.stop()

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        self.cover.set_position(100 - kwargs[ATTR_POSITION])

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        position = None
        if self.has_capability("position"):
            position = 100 - self.cover.get_position()
        return position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        is_closed = None
        if self.has_capability("position"):
            is_closed = self.cover.is_closed()
        return is_closed

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        orientation = None
        if self.has_capability("rotation"):
            orientation = 100 - self.cover.orientation
        return orientation

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        self.cover.orientation = kwargs[ATTR_TILT_POSITION]

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self.cover.orientation = 100

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self.cover.orientation = 0

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self.cover.stop()
