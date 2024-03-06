"""Support for deCONZ covers."""
from __future__ import annotations

from typing import Any, cast

from pydeconz.interfaces.lights import CoverAction
from pydeconz.models import ResourceType
from pydeconz.models.event import EventType
from pydeconz.models.light.cover import Cover

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

DECONZ_TYPE_TO_DEVICE_CLASS = {
    ResourceType.LEVEL_CONTROLLABLE_OUTPUT.value: CoverDeviceClass.DAMPER,
    ResourceType.WINDOW_COVERING_CONTROLLER.value: CoverDeviceClass.SHADE,
    ResourceType.WINDOW_COVERING_DEVICE.value: CoverDeviceClass.SHADE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up covers for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_cover(_: EventType, cover_id: str) -> None:
        """Add cover from deCONZ."""
        async_add_entities([DeconzCover(cover_id, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_cover,
        gateway.api.lights.covers,
    )


class DeconzCover(DeconzDevice[Cover], CoverEntity):
    """Representation of a deCONZ cover."""

    TYPE = DOMAIN

    def __init__(self, cover_id: str, gateway: DeconzGateway) -> None:
        """Set up cover device."""
        super().__init__(cover := gateway.api.lights.covers[cover_id], gateway)

        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

        if self._device.tilt is not None:
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
                | CoverEntityFeature.SET_TILT_POSITION
            )

        self._attr_device_class = DECONZ_TYPE_TO_DEVICE_CLASS.get(cover.type)

        self.legacy_mode = cover.type == ResourceType.LEVEL_CONTROLLABLE_OUTPUT.value

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover."""
        return 100 - self._device.lift

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return not self._device.is_open

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = 100 - cast(int, kwargs[ATTR_POSITION])
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            lift=position,
            legacy_mode=self.legacy_mode,
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            action=CoverAction.OPEN,
            legacy_mode=self.legacy_mode,
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            action=CoverAction.CLOSE,
            legacy_mode=self.legacy_mode,
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            action=CoverAction.STOP,
            legacy_mode=self.legacy_mode,
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position of the cover."""
        if self._device.tilt is not None:
            return 100 - self._device.tilt
        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Tilt the cover to a specific position."""
        position = 100 - cast(int, kwargs[ATTR_TILT_POSITION])
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            tilt=position,
            legacy_mode=self.legacy_mode,
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open cover tilt."""
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            tilt=0,
            legacy_mode=self.legacy_mode,
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            tilt=100,
            legacy_mode=self.legacy_mode,
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        await self.gateway.api.lights.covers.set_state(
            id=self._device.resource_id,
            action=CoverAction.STOP,
            legacy_mode=self.legacy_mode,
        )
