"""PG LAB Electronics Cover."""

from __future__ import annotations

from typing import Any

from pypglab.device import Device as PyPGLabDevice
from pypglab.shutter import Shutter as PyPGLabShutter

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .discovery import PGLabDiscovery
from .entity import PGLabEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches for device."""

    @callback
    def async_discover(
        pglab_device: PyPGLabDevice, pglab_shutter: PyPGLabShutter
    ) -> None:
        """Discover and add a PG LAB Cover."""
        pglab_discovery = config_entry.runtime_data
        pglab_cover = PGLabCover(pglab_discovery, pglab_device, pglab_shutter)
        async_add_entities([pglab_cover])

    # Register the callback to create the cover entity when discovered.
    pglab_discovery = config_entry.runtime_data
    await pglab_discovery.register_platform(hass, Platform.COVER, async_discover)


class PGLabCover(PGLabEntity, CoverEntity):
    """A PGLab Cover."""

    _attr_translation_key = "shutter"

    def __init__(
        self,
        pglab_discovery: PGLabDiscovery,
        pglab_device: PyPGLabDevice,
        pglab_shutter: PyPGLabShutter,
    ) -> None:
        """Initialize the Cover class."""

        super().__init__(
            pglab_discovery,
            pglab_device,
            pglab_shutter,
        )

        self._attr_unique_id = f"{pglab_device.id}_shutter{pglab_shutter.id}"
        self._attr_translation_placeholders = {"shutter_id": pglab_shutter.id}

        self._shutter = pglab_shutter

        self._attr_device_class = CoverDeviceClass.SHUTTER
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._shutter.open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._shutter.close()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._shutter.stop()

    @property
    def is_closed(self) -> bool | None:
        """Return if cover is closed."""
        if not self._shutter.state:
            return None
        return self._shutter.state == PyPGLabShutter.STATE_CLOSED

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if not self._shutter.state:
            return None
        return self._shutter.state == PyPGLabShutter.STATE_CLOSING

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if not self._shutter.state:
            return None
        return self._shutter.state == PyPGLabShutter.STATE_OPENING
