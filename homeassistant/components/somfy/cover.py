"""Support for Somfy Covers."""
from pymfy.api.devices.blind import Blind
from pymfy.api.devices.category import Category

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
)

from . import API, CONF_OPTIMISTIC, DEVICES, DOMAIN, SomfyEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy cover platform."""

    def get_covers():
        """Retrieve covers."""
        categories = {
            Category.ROLLER_SHUTTER.value,
            Category.INTERIOR_BLIND.value,
            Category.EXTERIOR_BLIND.value,
        }

        devices = hass.data[DOMAIN][DEVICES]

        return [
            SomfyCover(
                cover, hass.data[DOMAIN][API], hass.data[DOMAIN][CONF_OPTIMISTIC]
            )
            for cover in devices
            if categories & set(cover.categories)
        ]

    async_add_entities(await hass.async_add_executor_job(get_covers), True)


class SomfyCover(SomfyEntity, CoverEntity):
    """Representation of a Somfy cover device."""

    def __init__(self, device, api, optimistic):
        """Initialize the Somfy device."""
        super().__init__(device, api)
        self.cover = Blind(self.device, self.api)
        self.optimistic = optimistic
        self._closed = None

    async def async_update(self):
        """Update the device with the latest data."""
        await super().async_update()
        self.cover = Blind(self.device, self.api)

    def close_cover(self, **kwargs):
        """Close the cover."""
        if self.optimistic:
            self._closed = True
        self.cover.close()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self.optimistic:
            self._closed = False
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
        elif self.optimistic:
            is_closed = self._closed
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
        self.cover.orientation = 100 - kwargs[ATTR_TILT_POSITION]

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self.cover.orientation = 0

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self.cover.orientation = 100

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self.cover.stop()
