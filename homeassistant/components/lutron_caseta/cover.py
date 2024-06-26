"""Support for Lutron Caseta shades."""

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
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


class LutronCasetaShade(LutronCasetaDeviceUpdatableEntity, CoverEntity):
    """Representation of a Lutron shade with open/close functionality."""

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

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._smartbridge.lower_cover(self.device_id)
        await self.async_update()
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._smartbridge.stop_cover(self.device_id)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._smartbridge.raise_cover(self.device_id)
        await self.async_update()
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        await self._smartbridge.set_value(self.device_id, kwargs[ATTR_POSITION])


class LutronCasetaTiltOnlyBlind(LutronCasetaDeviceUpdatableEntity, CoverEntity):
    """Representation of a Lutron tilt only blind."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.OPEN_TILT
    )
    _attr_device_class = CoverDeviceClass.BLIND

    @property
    def is_closed(self) -> bool:
        """Return if the blind is closed, either at position 0 or 100."""
        return self._device["tilt"] == 0 or self._device["tilt"] == 100

    @property
    def current_cover_tilt_position(self) -> int:
        """Return the current tilt position of blind."""
        return self._device["tilt"]

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the blind."""
        await self._smartbridge.set_tilt(self.device_id, 0)
        await self.async_update()
        self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the blind."""
        await self._smartbridge.set_tilt(self.device_id, 50)
        await self.async_update()
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the blind to a specific tilt."""
        await self._smartbridge.set_tilt(self.device_id, kwargs[ATTR_TILT_POSITION])


PYLUTRON_TYPE_TO_CLASSES = {
    "SerenaTiltOnlyWoodBlind": LutronCasetaTiltOnlyBlind,
    "SerenaHoneycombShade": LutronCasetaShade,
    "SerenaRollerShade": LutronCasetaShade,
    "TriathlonHoneycombShade": LutronCasetaShade,
    "TriathlonRollerShade": LutronCasetaShade,
    "QsWirelessShade": LutronCasetaShade,
    "QsWirelessHorizontalSheerBlind": LutronCasetaShade,
    "Shade": LutronCasetaShade,
    "PalladiomWireFreeShade": LutronCasetaShade,
}


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
    cover_devices = bridge.get_devices_by_domain(DOMAIN)
    async_add_entities(
        # default to standard LutronCasetaCover type if the pylutron type is not yet mapped
        PYLUTRON_TYPE_TO_CLASSES.get(cover_device["type"], LutronCasetaShade)(
            cover_device, data
        )
        for cover_device in cover_devices
    )
