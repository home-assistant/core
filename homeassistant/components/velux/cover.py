"""Support for Velux covers."""
from __future__ import annotations

from typing import Any, cast

from pyvlx import OpeningDevice, Position
from pyvlx.opening_device import Awning, Blind, GarageDoor, Gate, RollerShutter, Window

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_VELUX, VeluxEntity

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover(s) for Velux platform."""
    entities = []
    for node in hass.data[DATA_VELUX].pyvlx.nodes:
        if isinstance(node, OpeningDevice):
            entities.append(VeluxCover(node))
    async_add_entities(entities)


class VeluxCover(VeluxEntity, CoverEntity):
    """Representation of a Velux cover."""

    _is_blind = False
    node: OpeningDevice

    def __init__(self, node: OpeningDevice) -> None:
        """Initialize VeluxCover."""
        super().__init__(node)
        self._attr_device_class = CoverDeviceClass.WINDOW
        if isinstance(node, Awning):
            self._attr_device_class = CoverDeviceClass.AWNING
        if isinstance(node, Blind):
            self._attr_device_class = CoverDeviceClass.BLIND
            self._is_blind = True
        if isinstance(node, GarageDoor):
            self._attr_device_class = CoverDeviceClass.GARAGE
        if isinstance(node, Gate):
            self._attr_device_class = CoverDeviceClass.GATE
        if isinstance(node, RollerShutter):
            self._attr_device_class = CoverDeviceClass.SHUTTER
        if isinstance(node, Window):
            self._attr_device_class = CoverDeviceClass.WINDOW

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )
        if self.current_cover_tilt_position is not None:
            supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
                | CoverEntityFeature.STOP_TILT
            )
        return supported_features

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover."""
        return 100 - self.node.position.position_percent

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current position of the cover."""
        if self._is_blind:
            return 100 - cast(Blind, self.node).orientation.position_percent
        return None

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.node.position.closed

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.node.close(wait_for_completion=False)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.node.open(wait_for_completion=False)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percent = 100 - kwargs[ATTR_POSITION]

        await self.node.set_position(
            Position(position_percent=position_percent), wait_for_completion=False
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.node.stop(wait_for_completion=False)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await cast(Blind, self.node).close_orientation(wait_for_completion=False)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open cover tilt."""
        await cast(Blind, self.node).open_orientation(wait_for_completion=False)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        await cast(Blind, self.node).stop_orientation(wait_for_completion=False)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move cover tilt to a specific position."""
        position_percent = 100 - kwargs[ATTR_TILT_POSITION]
        orientation = Position(position_percent=position_percent)
        await cast(Blind, self.node).set_orientation(
            orientation=orientation, wait_for_completion=False
        )
