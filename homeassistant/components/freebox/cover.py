"""Support for Freebox covers."""
from __future__ import annotations

import base64
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .home_base import FreeboxHomeEntity
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up covers."""
    router = hass.data[DOMAIN][entry.unique_id]
    tracked: set = set()

    @callback
    def update_callback():
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()


@callback
def add_entities(
    hass: HomeAssistant,
    router: FreeboxRouter,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
):
    """Add new covers from the router."""
    new_trackedshutter = []
    new_trackedbasic = []

    for nodeid, node in router.home_devices.items():
        if nodeid in tracked:
            continue
        if node["category"] == "basic_shutter":
            new_trackedbasic.append(FreeboxBasicShutter(hass, router, node))
            tracked.add(nodeid)
        elif node["category"] == "shutter" or node["category"] == "opener":
            new_trackedshutter.append(FreeboxShutter(hass, router, node))
            tracked.add(nodeid)

    if new_trackedshutter:
        async_add_entities(new_trackedshutter, True)
    if new_trackedbasic:
        async_add_entities(new_trackedbasic, True)


class FreeboxBasicShutter(FreeboxHomeEntity, CoverEntity):
    """Representation of a Freebox cover."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a cover."""
        super().__init__(hass, router, node)
        self._command_up = self.get_command_id(node["show_endpoints"], "slot", "up")
        self._command_stop = self.get_command_id(node["show_endpoints"], "slot", "stop")
        self._command_down = self.get_command_id(node["show_endpoints"], "slot", "down")
        self._command_state = self.get_command_id(
            node["show_endpoints"], "signal", "state"
        )
        self._state = self.convert_state(self.get_value("signal", "state"))

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the device_class."""
        return CoverDeviceClass.SHUTTER

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._state == STATE_OPEN:
            return False
        if self._state == STATE_CLOSED:
            return True
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self.set_home_endpoint_value(self._command_up)
        await self.async_set_value("signal", "state", False)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.set_home_endpoint_value(self._command_down)
        await self.async_set_value("signal", "state", True)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        await self.set_home_endpoint_value(self._command_stop)
        await self.async_set_value("signal", "state", None)

    async def async_update_node(self) -> None:
        """Update state."""
        self._state = self.convert_state(self.get_value("signal", "state"))

    def convert_state(self, state) -> str:
        """Convert state."""
        if state:
            return STATE_CLOSED
        # state is not None
        return STATE_OPEN


class FreeboxShutter(FreeboxHomeEntity, CoverEntity):
    """Representation of a Freebox cover."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize a cover."""
        # For the dev I got
        # DEVICE_CLASS_SHUTTER  = RTS
        # DEVICE_CLASS_GARAGE   = IOHome
        super().__init__(hass, router, node)
        self._command_set_position = self.get_command_id(
            node["show_endpoints"], "slot", "position_set"
        )
        self._command_stop = self.get_command_id(node["show_endpoints"], "slot", "stop")
        self._command_position = self.get_command_id(
            node["type"]["endpoints"], "slot", "position"
        )
        self._device_class = CoverDeviceClass.SHUTTER
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
            | CoverEntityFeature.STOP
        )
        self._invert_position = True

        if node["category"] == "opener":
            self._device_class = CoverDeviceClass.AWNING

            if "Porte_Garage" in node["type"]["icon"]:  # Dexxo Smart IO
                self._invert_position = False
                self._device_class = CoverDeviceClass.GARAGE

        self._attr_current_cover_position: Any
        self.update_current_position()

    @property
    def device_class(self) -> CoverDeviceClass:
        """Return the device_class."""
        return self._device_class

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._attr_current_cover_position == 0

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        value = (
            100 - kwargs[ATTR_POSITION]
            if (self._invert_position)
            else kwargs[ATTR_POSITION]
        )
        await self.set_home_endpoint_value(self._command_set_position, value)
        self._attr_current_cover_position = kwargs[ATTR_POSITION]
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        value = 0 if (self._invert_position) else 100
        await self.set_home_endpoint_value(self._command_set_position, value)
        self._attr_current_cover_position = 100
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        value = 100 if (self._invert_position) else 0
        await self.set_home_endpoint_value(self._command_set_position, value)
        self._attr_current_cover_position = 0
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        await self.set_home_endpoint_value(self._command_stop)
        self.update_current_position()
        self.async_write_ha_state()

    def update_current_position(self):
        """Set the current position."""
        # Parse current status
        state = self.get_value("signal", "state")
        position_set = self.get_value("signal", "position_set")

        hex_value = base64.b64decode(state).hex()
        if len(hex_value) != 118:
            _LOGGER.warning("Invalid state: %s", str(state))
            # Use basic method to set position
            self._attr_current_cover_position = (
                (100 - position_set) if self._invert_position else position_set
            )
            return

        # Get the two important values
        val_1 = hex_value[96:98]
        val_2 = hex_value[100:102]

        # Open
        if val_2 == "00":
            self._attr_current_cover_position = 100
        # Close
        elif val_2 == "c8":
            self._attr_current_cover_position = 0
        else:
            # Check if the position current value can be used
            if 0 < position_set < 100:
                self._attr_current_cover_position = (
                    (100 - position_set) if self._invert_position else position_set
                )
            else:  # set 50% (because why not!)
                self._attr_current_cover_position = 50

        # Dump
        _LOGGER.debug(
            "Details [%s-%s/%s/%s] with state: %s ",
            str(self._attr_current_cover_position),
            str(position_set),
            val_1,
            val_2,
            str(state),
        )

    async def async_update_node(self):
        """Update node."""
        self.update_current_position()
