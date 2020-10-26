"""Support for Somfy Covers."""

from pymfy.api.devices.blind import Blind
from pymfy.api.devices.category import Category
import requests

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_SHUTTER,
    CoverEntity,
)
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.helpers.restore_state import RestoreEntity

from . import API, CONF_OPTIMISTIC, DEVICES, DOMAIN, SomfyEntity

BLIND_DEVICE_CATAGORIES = {Category.INTERIOR_BLIND.value, Category.EXTERIOR_BLIND.value}
SHUTTER_DEVICE_CATAGORIES = {Category.EXTERIOR_BLIND.value}
SUPPORTED_CATAGORIES = {
    Category.ROLLER_SHUTTER.value,
    Category.INTERIOR_BLIND.value,
    Category.EXTERIOR_BLIND.value,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy cover platform."""

    def get_covers():
        """Retrieve covers."""
        devices = hass.data[DOMAIN][DEVICES]

        return [
            SomfyCover(
                cover, hass.data[DOMAIN][API], hass.data[DOMAIN][CONF_OPTIMISTIC]
            )
            for cover in devices
            if SUPPORTED_CATAGORIES & set(cover.categories)
        ]

    async_add_entities(await hass.async_add_executor_job(get_covers))


class SomfyCover(SomfyEntity, RestoreEntity, CoverEntity):
    """Representation of a Somfy cover device."""

    def __init__(self, device, api, optimistic):
        """Initialize the Somfy device."""
        super().__init__(device, api)
        self.cover = Blind(self.device, self.api)
        self.categories = set(device.categories)
        self.optimistic = optimistic
        self._closed = None
        self._is_opening = None
        self._is_closing = None

    async def async_update(self):
        """Update the device with the latest data."""
        await super().async_update()
        self.cover = Blind(self.device, self.api)

    def close_cover(self, **kwargs):
        """Close the cover."""
        self._is_closing = True
        try:
            # Blocks until the close command is sent
            self.cover.close()
            self._closed = True
        except requests.exceptions.HTTPError:
            raise
        finally:
            self._is_closing = False

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._is_opening = True
        try:
            # Blocks until the open command is sent
            self.cover.open()
            self._closed = False
        except requests.exceptions.HTTPError:
            raise
        finally:
            self._is_opening = False

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.cover.stop()

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        self.cover.set_position(100 - kwargs[ATTR_POSITION])

    @property
    def device_class(self):
        """Return the device class."""
        if self.categories & BLIND_DEVICE_CATAGORIES:
            return DEVICE_CLASS_BLIND
        if self.categories & SHUTTER_DEVICE_CATAGORIES:
            return DEVICE_CLASS_SHUTTER
        return None

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        position = None
        if self.has_capability("position"):
            position = 100 - self.cover.get_position()
        return position

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        if not self.optimistic:
            return None
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        if not self.optimistic:
            return None
        return self._is_closing

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

    async def async_added_to_hass(self):
        """Complete the initialization."""
        await super().async_added_to_hass()
        if self.optimistic:
            # Restore the last state if we use optimistic
            last_state = await self.async_get_last_state()

            if last_state is not None and last_state.state in (
                STATE_OPEN,
                STATE_CLOSED,
            ):
                self._closed = last_state.state == STATE_CLOSED

        await self.async_update()
