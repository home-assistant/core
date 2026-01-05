"""Support for Velux covers."""

from __future__ import annotations

from typing import Any, cast

from pyvlx import (
    Awning,
    Blind,
    GarageDoor,
    Gate,
    OpeningDevice,
    Position,
    RollerShutter,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .entity import VeluxEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover(s) for Velux platform."""
    pyvlx = config_entry.runtime_data
    async_add_entities(
        VeluxCover(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, OpeningDevice)
    )


class VeluxCover(VeluxEntity, CoverEntity):
    """Representation of a Velux cover."""

    _is_blind = False
    node: OpeningDevice

    # Do not name the "main" feature of the device (position control)
    _attr_name = None

    def __init__(self, node: OpeningDevice, config_entry_id: str) -> None:
        """Initialize VeluxCover."""
        super().__init__(node, config_entry_id)
        # Features common to all covers
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )
        # Window is the default device class for covers
        self._attr_device_class = CoverDeviceClass.WINDOW
        if isinstance(node, Awning):
            self._attr_device_class = CoverDeviceClass.AWNING
        if isinstance(node, GarageDoor):
            self._attr_device_class = CoverDeviceClass.GARAGE
        if isinstance(node, Gate):
            self._attr_device_class = CoverDeviceClass.GATE
        if isinstance(node, RollerShutter):
            self._attr_device_class = CoverDeviceClass.SHUTTER
        if isinstance(node, Blind):
            self._attr_device_class = CoverDeviceClass.BLIND
            self._is_blind = True
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.SET_TILT_POSITION
                | CoverEntityFeature.STOP_TILT
            )

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
        # do not use the node's closed state but rely on cover position
        # until https://github.com/Julius2342/pyvlx/pull/543 is merged.
        # once merged this can again return self.node.position.closed
        return self.current_cover_position == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.node.is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.node.is_closing

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
