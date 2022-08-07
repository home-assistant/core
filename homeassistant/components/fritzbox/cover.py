"""Support for AVM FRITZ!SmartHome cover devices."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxEntity
from .const import CONF_COORDINATOR, DOMAIN as FRITZBOX_DOMAIN

OPERATION_LIST = [
    CoverEntityFeature.OPEN,
    CoverEntityFeature.CLOSE,
    CoverEntityFeature.STOP,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome cover from ConfigEntry."""
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    async_add_entities(
        [
            FritzboxCover(coordinator, ain)
            for ain, device in coordinator.data.items()
            if device.has_blind
        ]
    )


class FritzboxCover(FritzBoxEntity, CoverEntity):
    """The cover class for FRITZ!SmartHome covers."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
    )

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position."""
        position = None
        if self.device.has_blind and self.device.levelpercentage is not None:
            position = 100 - self.device.levelpercentage
        return position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        closed = False
        if self.device.has_blind and self.device.levelpercentage is not None:
            closed = self.device.levelpercentage == 100
        return closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.hass.async_add_executor_job(self.device.set_blind_open)
        await self.coordinator.async_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.hass.async_add_executor_job(self.device.set_blind_close)
        await self.coordinator.async_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if kwargs.get(ATTR_POSITION) is not None:
            position = kwargs[ATTR_POSITION]
            await self.hass.async_add_executor_job(
                self.device.set_level_percentage, 100 - position
            )
        await self.coordinator.async_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.hass.async_add_executor_job(self.device.set_blind_stop)
        await self.coordinator.async_refresh()
