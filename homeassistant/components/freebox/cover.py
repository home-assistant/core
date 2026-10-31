"""Support for Freebox covers (shutters)."""

import logging
from typing import Any, override

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FreeboxHomeCategory
from .entity import FreeboxHomeEntity
from .router import FreeboxConfigEntry, FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Freebox cover entities."""
    router = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def update_callback() -> None:
        """Add newly discovered covers."""
        add_entities(router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()


@callback
def add_entities(
    router: FreeboxRouter,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new covers from the router."""
    new_entities: list[FreeboxCover] = []

    for node_id, node in router.home_devices.items():
        if node["category"] != FreeboxHomeCategory.SHUTTER or node_id in tracked:
            continue
        new_entities.append(FreeboxCover(router, node))
        tracked.add(node_id)

    if new_entities:
        async_add_entities(new_entities, True)


class FreeboxCover(FreeboxHomeEntity, CoverEntity):
    """Representation of a Freebox cover (shutter)."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, router: FreeboxRouter, node: dict[str, Any]) -> None:
        """Initialize the cover."""
        super().__init__(router, node)

        endpoints = node["type"]["endpoints"]
        self._command_set_position = self.get_command_id(
            endpoints, "slot", "position_set"
        )
        self._command_stop = self.get_command_id(endpoints, "slot", "stop")
        self._command_state = self.get_command_id(endpoints, "signal", "position_set")

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover.

        100 is fully open, 0 is fully closed.
        """
        return self._attr_current_cover_position

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._attr_current_cover_position is None:
            return None
        return self._attr_current_cover_position == 0

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (Freebox position 0)."""
        await self.set_home_endpoint_value(self._command_set_position, 0)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (Freebox position 100)."""
        await self.set_home_endpoint_value(self._command_set_position, 100)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.set_home_endpoint_value(self._command_stop, None)

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position (inversion HA <-> Freebox)."""
        ha_position = kwargs["position"]
        fbx_position = 100 - ha_position
        await self.set_home_endpoint_value(self._command_set_position, fbx_position)

    async def async_update(self) -> None:
        """Update cover state and position."""
        fbx_pos = await self.get_home_endpoint_value(self._command_state)
        if fbx_pos is not None:
            self._attr_current_cover_position = 100 - int(fbx_pos)
        else:
            self._attr_current_cover_position = None
