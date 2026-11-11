"""Support for Freebox covers (shutters)."""

import base64
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
    new_entities: list[CoverEntity] = []

    for node_id, node in router.home_devices.items():
        if node_id in tracked:
            continue
        category = node["category"]
        if category == FreeboxHomeCategory.BASIC_SHUTTER:
            new_entities.append(FreeboxBasicShutter(router, node))
            tracked.add(node_id)
        elif category in (FreeboxHomeCategory.SHUTTER, FreeboxHomeCategory.OPENER):
            endpoints = node.get("type", {}).get("endpoints", [])
            has_position = any(
                ep.get("name") in ("position_set", "position")
                and ep.get("ep_type") == "slot"
                for ep in endpoints
            )
            if has_position:
                new_entities.append(FreeboxCover(router, node))
            else:
                new_entities.append(FreeboxBasicShutter(router, node))
            tracked.add(node_id)

    if new_entities:
        async_add_entities(new_entities)


class FreeboxBasicShutter(FreeboxHomeEntity, CoverEntity):
    """Representation of a Freebox basic cover (RTS shutter without position)."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_name = None
    _attr_should_poll = False
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, router: FreeboxRouter, node: dict[str, Any]) -> None:
        """Initialize the basic shutter."""
        super().__init__(router, node)

        endpoints = node["type"]["endpoints"]
        self._command_up = self.get_command_id(endpoints, "slot", "up")
        self._command_down = self.get_command_id(endpoints, "slot", "down")
        self._command_stop = self.get_command_id(endpoints, "slot", "stop")
        self._attr_is_closed = self._to_closed(self.get_value("signal", "state"))

    @staticmethod
    def _to_closed(state: Any) -> bool | None:
        """Return if closed according to state signal."""
        return None if state is None else bool(state)

    @override
    async def async_update_signal(self) -> None:
        """Update from router signals."""
        self._node = self._router.home_devices[self._id]
        self._attr_is_closed = self._to_closed(self.get_value("signal", "state"))
        await super().async_update_signal()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shutter."""
        await self.set_home_endpoint_value(self._command_up)
        self._attr_is_closed = False
        self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shutter."""
        await self.set_home_endpoint_value(self._command_down)
        self._attr_is_closed = True
        self.async_write_ha_state()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the shutter."""
        await self.set_home_endpoint_value(self._command_stop)
        self._attr_is_closed = None
        self.async_write_ha_state()


class FreeboxCover(FreeboxHomeEntity, CoverEntity):
    """Representation of a Freebox cover (shutter with position)."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_name = None
    _attr_should_poll = False
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
        self._invert_position = True
        if node["category"] == FreeboxHomeCategory.OPENER:
            if "Porte_Garage" in node.get("type", {}).get("icon", ""):
                self._invert_position = False
                self._attr_device_class = CoverDeviceClass.GARAGE
            else:
                self._attr_device_class = CoverDeviceClass.AWNING

        self._update_current_position()

    def _to_freebox(self, position: int) -> int:
        """Convert HA position to Freebox position."""
        return 100 - position if self._invert_position else position

    def _to_ha(self, position: int) -> int:
        """Convert Freebox position to HA position."""
        return 100 - position if self._invert_position else position

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
    async def async_update_signal(self) -> None:
        """Update from router signals."""
        self._node = self._router.home_devices[self._id]
        self._update_current_position()
        await super().async_update_signal()

    def _update_current_position(self) -> None:
        """Read position from node signals."""
        state = self.get_value("signal", "state")
        position_set = self.get_value("signal", "position_set")
        if position_set is None:
            self._attr_current_cover_position = None
            return

        try:
            hex_value = base64.b64decode(state).hex() if state else ""
        except TypeError:
            hex_value = ""
        except ValueError:
            hex_value = ""

        if len(hex_value) != 118:
            self._attr_current_cover_position = self._to_ha(int(position_set))
            return

        # Byte 50 in state frame: 00 = open, c8 = closed
        flag = hex_value[100:102]
        if flag == "00":
            self._attr_current_cover_position = self._to_ha(0)
        elif flag == "c8":
            self._attr_current_cover_position = self._to_ha(100)
        elif 0 < int(position_set) < 100:
            self._attr_current_cover_position = self._to_ha(int(position_set))
        else:
            self._attr_current_cover_position = 50

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        ha_position = kwargs["position"]
        await self.set_home_endpoint_value(
            self._command_set_position, self._to_freebox(ha_position)
        )
        self._attr_current_cover_position = ha_position
        self.async_write_ha_state()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.async_set_cover_position(position=100)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.async_set_cover_position(position=0)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        await self.set_home_endpoint_value(self._command_stop, None)
        self._update_current_position()
        self.async_write_ha_state()
