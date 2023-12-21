"""Support for Velux covers."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import inspect
import logging
from typing import Any

from pyvlx import Position, PyVLX
from pyvlx.api.get_limitation import GetLimitation
from pyvlx.exception import PyVLXException
from pyvlx.node import Node
from pyvlx.opening_device import (
    Awning,
    Blind,
    GarageDoor,
    Gate,
    OpeningDevice,
    RollerShutter,
    Window,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .node_entity import VeluxNodeEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up cover(s) for Velux platform."""
    entities: list = []
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    for node in pyvlx.nodes:
        if isinstance(node, Window):
            _LOGGER.debug("Window will be added: %s", node.name)
            entities.append(VeluxWindow(hass, node))
        elif isinstance(node, Blind):
            _LOGGER.debug("Blind will be added: %s", node.name)
            entities.append(VeluxBlind(node))
        elif isinstance(node, OpeningDevice):
            _LOGGER.debug("Cover will be added: %s", node.name)
            entities.append(VeluxCover(node))
    async_add_entities(entities)


class VeluxCover(VeluxNodeEntity, CoverEntity):
    """Representation of a Velux cover."""

    def __init__(self, node: OpeningDevice) -> None:
        """Initialize VeluxCover."""
        super().__init__(node)
        self.node: OpeningDevice = node
        if isinstance(node, Awning):
            self._attr_device_class = CoverDeviceClass.AWNING
        if isinstance(node, GarageDoor):
            self._attr_device_class = CoverDeviceClass.GARAGE
        if isinstance(node, Gate):
            self._attr_device_class = CoverDeviceClass.GATE
        if isinstance(node, RollerShutter):
            self._attr_device_class = CoverDeviceClass.SHUTTER
        self.is_looping_while_moving: bool = False

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover."""
        return 100 - self.node.get_position().position_percent

    @property
    def is_closed(self) -> bool:
        """Return true if the cover is closed."""
        return self.node.position.closed

    @property
    def is_opening(self) -> bool:
        """Return if the cover is closing or not."""
        return self.node.is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is opening or not."""
        return self.node.is_closing

    async def after_update_callback(self, node: Node) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()
        if self.node.is_moving():
            if not self.is_looping_while_moving:
                self.is_looping_while_moving = True
                while self.node.is_moving():
                    await asyncio.sleep(1)
                    self.async_write_ha_state()
                self.is_looping_while_moving = False

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        close_args: dict[str, Any] = {"wait_for_completion": False}
        if (
            "velocity" in kwargs
            and "velocity" in inspect.getfullargspec(self.node.close).args
        ):
            close_args["velocity"] = kwargs["velocity"]
        await self.node.close(**close_args)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        open_args: dict[str, Any] = {"wait_for_completion": False}
        if (
            "velocity" in kwargs
            and "velocity" in inspect.getfullargspec(self.node.open).args
        ):
            open_args["velocity"] = kwargs["velocity"]
        await self.node.open(**open_args)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position_percent: int = 100 - kwargs[ATTR_POSITION]
            position: Position = Position(position_percent=position_percent)
            set_pos_args: dict[str, Any] = {"wait_for_completion": False}
            if (
                "velocity" in kwargs
                and "velocity" in inspect.getfullargspec(self.node.set_position).args
            ):
                set_pos_args["velocity"] = kwargs["velocity"]
            await self.node.set_position(position, **set_pos_args)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.node.stop(wait_for_completion=False)


class VeluxBlind(VeluxCover):
    """Representation of a Velux blind."""

    def __init__(self, node: Blind) -> None:
        """Initialize Velux blind."""
        super().__init__(node)
        self.node: Blind = node
        self._attr_device_class = CoverDeviceClass.BLIND
        self._is_blind = True

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
            | CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.STOP_TILT
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current position of the cover."""
        return 100 - self.node.orientation.position_percent

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self.node.close_orientation(wait_for_completion=False)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open cover tilt."""
        await self.node.open_orientation(wait_for_completion=False)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        await self.node.stop_orientation(wait_for_completion=False)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move cover tilt to a specific position."""
        position_percent: int = 100 - kwargs[ATTR_TILT_POSITION]
        orientation: Position = Position(position_percent=position_percent)
        await self.node.set_orientation(
            orientation=orientation, wait_for_completion=False
        )


class VeluxWindow(VeluxCover):
    """Representation of a Velux window."""

    def __init__(self, hass: HomeAssistant, node: Window) -> None:
        """Initialize Velux window."""
        super().__init__(node)
        self.node: Window = node
        self._attr_device_class = CoverDeviceClass.WINDOW
        self._hass: HomeAssistant = hass
        self._extra_attr_limitation_min: int | None = None
        self._extra_attr_limitation_max: int | None = None

        self.coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=self.unique_id,
            update_method=self.async_update_limitation,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def async_init(self) -> None:
        """Async initialize."""
        return await self.coordinator.async_config_entry_first_refresh()

    async def async_update_limitation(self) -> None:
        """Get the updated status of the cover (limitations only)."""
        try:
            limitation: GetLimitation = await self.node.get_limitation()
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
