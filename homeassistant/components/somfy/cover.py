"""Support for Somfy Covers."""

from pymfy.api.devices.blind import Blind
from pymfy.api.devices.category import Category

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_SHUTTER,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.const import CONF_OPTIMISTIC, STATE_CLOSED, STATE_OPEN
from homeassistant.helpers.restore_state import RestoreEntity

from . import SomfyEntity
from .const import API, COORDINATOR, DOMAIN

BLIND_DEVICE_CATEGORIES = {Category.INTERIOR_BLIND.value, Category.EXTERIOR_BLIND.value}
SHUTTER_DEVICE_CATEGORIES = {Category.EXTERIOR_BLIND.value}
SUPPORTED_CATEGORIES = {
    Category.ROLLER_SHUTTER.value,
    Category.INTERIOR_BLIND.value,
    Category.EXTERIOR_BLIND.value,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy cover platform."""
    domain_data = hass.data[DOMAIN]
    coordinator = domain_data[COORDINATOR]
    api = domain_data[API]

    covers = [
        SomfyCover(coordinator, device_id, api, domain_data[CONF_OPTIMISTIC])
        for device_id, device in coordinator.data.items()
        if SUPPORTED_CATEGORIES & set(device.categories)
    ]

    async_add_entities(covers)


class SomfyCover(SomfyEntity, RestoreEntity, CoverEntity):
    """Representation of a Somfy cover device."""

    def __init__(self, coordinator, device_id, api, optimistic):
        """Initialize the Somfy device."""
        super().__init__(coordinator, device_id, api)
        self.categories = set(self.device.categories)
        self.optimistic = optimistic
        self._closed = None
        self._is_opening = None
        self._is_closing = None
        self._cover = None
        self._create_device()

    def _create_device(self) -> Blind:
        """Update the device with the latest data."""
        self._cover = Blind(self.device, self.api)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        supported_features = 0
        if self.has_capability("open"):
            supported_features |= SUPPORT_OPEN
        if self.has_capability("close"):
            supported_features |= SUPPORT_CLOSE
        if self.has_capability("stop"):
            supported_features |= SUPPORT_STOP
        if self.has_capability("position"):
            supported_features |= SUPPORT_SET_POSITION
        if self.has_capability("rotation"):
            supported_features |= (
                SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_STOP_TILT
                | SUPPORT_SET_TILT_POSITION
            )

        return supported_features

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._is_closing = True
        self.async_write_ha_state()
        try:
            # Blocks until the close command is sent
            await self.hass.async_add_executor_job(self._cover.close)
            self._closed = True
        finally:
            self._is_closing = None
            self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._is_opening = True
        self.async_write_ha_state()
        try:
            # Blocks until the open command is sent
            await self.hass.async_add_executor_job(self._cover.open)
            self._closed = False
        finally:
            self._is_opening = None
            self.async_write_ha_state()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._cover.stop()

    def set_cover_position(self, **kwargs):
        """Move the cover shutter to a specific position."""
        self._cover.set_position(100 - kwargs[ATTR_POSITION])

    @property
    def device_class(self):
        """Return the device class."""
        if self.categories & BLIND_DEVICE_CATEGORIES:
            return DEVICE_CLASS_BLIND
        if self.categories & SHUTTER_DEVICE_CATEGORIES:
            return DEVICE_CLASS_SHUTTER
        return None

    @property
    def current_cover_position(self):
        """Return the current position of cover shutter."""
        if not self.has_state("position"):
            return None
        return 100 - self._cover.get_position()

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
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        is_closed = None
        if self.has_state("position"):
            is_closed = self._cover.is_closed()
        elif self.optimistic:
            is_closed = self._closed
        return is_closed

    @property
    def current_cover_tilt_position(self) -> int:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if not self.has_state("orientation"):
            return None
        return 100 - self._cover.orientation

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        self._cover.orientation = 100 - kwargs[ATTR_TILT_POSITION]

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self._cover.orientation = 0

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self._cover.orientation = 100

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        self._cover.stop()

    async def async_added_to_hass(self):
        """Complete the initialization."""
        await super().async_added_to_hass()
        if not self.optimistic:
            return
        # Restore the last state if we use optimistic
        last_state = await self.async_get_last_state()

        if last_state is not None and last_state.state in (
            STATE_OPEN,
            STATE_CLOSED,
        ):
            self._closed = last_state.state == STATE_CLOSED
