"""Support for Lutron Caseta shades."""

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDeviceUpdatableEntity
from .const import DOMAIN as CASETA_DOMAIN
from .models import LutronCasetaData


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta cover platform.

    Adds shades from the Caseta bridge associated with the config_entry as
    cover entities.
    """
    data: LutronCasetaData = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data.bridge
    bridge_device = data.bridge_device
    cover_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(
        LutronCasetaCover(cover_device, bridge, bridge_device)
        for cover_device in cover_devices
    )


class LutronCasetaCover(LutronCasetaDeviceUpdatableEntity, CoverEntity):
    """Representation of a Lutron shade."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_device_class = CoverDeviceClass.SHADE

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self._device["current_state"] < 1

    @property
    def current_cover_position(self) -> int:
        """Return the current position of cover."""
        return self._device["current_state"]

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Top the cover."""
        await self._smartbridge.stop_cover(self.device_id)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._smartbridge.lower_cover(self.device_id)
        await self.async_update()
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._smartbridge.raise_cover(self.device_id)
        await self.async_update()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self._smartbridge.set_value(self.device_id, position)
