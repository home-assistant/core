"""PG LAB Electronics Cover."""
from __future__ import annotations

from typing import Any

from pypglab.device import Device
from pypglab.shutter import Shutter

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CREATE_NEW_ENTITY, DISCONNECT_COMPONENT
from .entity import BaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for device."""

    @callback
    def async_discover(pglab_device: Device, pglab_shutter: Shutter) -> None:
        """Discover and add a PG LAB Relay."""
        pglab_cover = PgLab_Cover(pglab_device, pglab_shutter)
        async_add_entities([pglab_cover])

    hass.data[DISCONNECT_COMPONENT[Platform.COVER]] = async_dispatcher_connect(
        hass, CREATE_NEW_ENTITY[Platform.COVER], async_discover
    )


class PgLab_Cover(BaseEntity, CoverEntity):
    """A PG LAB Cover."""

    def __init__(self, pglab_device: Device, pglab_shutter: Shutter) -> None:
        """Initialize the Switch class."""

        super().__init__(
            platform=Platform.COVER, device=pglab_device, entity=pglab_shutter
        )

        self._attr_unique_id = f"{pglab_device.id}_shutter{pglab_shutter.id}_cover"
        self._attr_name = f"{pglab_device.name}_shutter{pglab_shutter.id}"

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
        """If cover is closed."""
        if not self._shutter.state:
            return None
        return self._shutter.state == Shutter.STATE_CLOSED

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._shutter.state == Shutter.STATE_CLOSING

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._shutter.state == Shutter.STATE_OPENING
