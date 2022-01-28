"""Support for Velux covers."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pyvlx import OpeningDevice, Position
from pyvlx.exception import PyVLXException
from pyvlx.opening_device import Awning, Blind, GarageDoor, Gate, RollerShutter, Window

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DATA_VELUX, VeluxEntity

if TYPE_CHECKING:
    from pyvlx.node import Node

DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up cover(s) for Velux platform."""
    entities: list[VeluxWindow | VeluxCover] = []

    for node in hass.data[DATA_VELUX].pyvlx.nodes:
        if isinstance(node, OpeningDevice):
            if isinstance(node, Window):
                entities.append(VeluxWindow(hass, node))
            else:
                entities.append(VeluxCover(node))

    for entity in entities:
        await entity.async_init()

    async_add_entities(entities)


class VeluxCover(VeluxEntity, CoverEntity):
    """Representation of a Velux cover."""

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP
        )
        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_SET_TILT_POSITION
                | SUPPORT_STOP_TILT
            )
        return supported_features

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return 100 - self.node.position.position_percent

    @property
    def current_cover_tilt_position(self):
        """Return the current position of the cover."""
        if isinstance(self.node, Blind):
            return 100 - self.node.orientation.position_percent
        return None

    @property
    def device_class(self):
        """Define this cover as either awning, blind, garage, gate, shutter or window."""
        if isinstance(self.node, Awning):
            return CoverDeviceClass.AWNING
        if isinstance(self.node, Blind):
            return CoverDeviceClass.BLIND
        if isinstance(self.node, GarageDoor):
            return CoverDeviceClass.GARAGE
        if isinstance(self.node, Gate):
            return CoverDeviceClass.GATE
        if isinstance(self.node, RollerShutter):
            return CoverDeviceClass.SHUTTER
        if isinstance(self.node, Window):
            return CoverDeviceClass.WINDOW
        return CoverDeviceClass.WINDOW

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.node.position.closed

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self.node.close(wait_for_completion=False)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.node.open(wait_for_completion=False)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position_percent = 100 - kwargs[ATTR_POSITION]

            await self.node.set_position(
                Position(position_percent=position_percent), wait_for_completion=False
            )

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.node.stop(wait_for_completion=False)

    async def async_close_cover_tilt(self, **kwargs):
        """Close cover tilt."""
        await self.node.close_orientation(wait_for_completion=False)

    async def async_open_cover_tilt(self, **kwargs):
        """Open cover tilt."""
        await self.node.open_orientation(wait_for_completion=False)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        await self.node.stop_orientation(wait_for_completion=False)

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move cover tilt to a specific position."""
        position_percent = 100 - kwargs[ATTR_TILT_POSITION]
        orientation = Position(position_percent=position_percent)
        await self.node.set_orientation(
            orientation=orientation, wait_for_completion=False
        )


class VeluxWindow(VeluxCover):
    """Representation of a Velux window."""

    def __init__(self, hass: HomeAssistant, node: Node) -> None:
        """Initialize Velux window."""
        super().__init__(node)
        self._hass = hass
        self._extra_attr_limitation_min: int | None = None
        self._extra_attr_limitation_max: int | None = None

        self.coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=self.unique_id,
            update_method=self.async_update_limitation,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def async_init(self):
        """Async initialize."""
        return await self.coordinator.async_config_entry_first_refresh()

    async def async_update_limitation(self):
        """Get the updated status of the cover (limitations only)."""
        try:
            limitation = await self.node.get_limitation()
            self._extra_attr_limitation_min = limitation.min_value
            self._extra_attr_limitation_max = limitation.max_value
        except PyVLXException:
            _LOGGER.error("Error fetch limitation data for cover %s", self.name)

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Return the state attributes."""
        return {
            "limitation_min": self._extra_attr_limitation_min,
            "limitation_max": self._extra_attr_limitation_max,
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()
