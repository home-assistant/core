"""Support for MySensors covers."""

from __future__ import annotations

from enum import Enum, unique
from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import setup_mysensors_platform
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .entity import MySensorsChildEntity


@unique
class CoverState(Enum):
    """An enumeration of the standard cover states."""

    OPEN = 0
    OPENING = 1
    CLOSING = 2
    CLOSED = 3


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors cover."""
        setup_mysensors_platform(
            hass,
            Platform.COVER,
            discovery_info,
            MySensorsCover,
            async_add_entities=async_add_entities,
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.COVER),
            async_discover,
        ),
    )


class MySensorsCover(MySensorsChildEntity, CoverEntity):
    """Representation of the value of a MySensors Cover child node."""

    def get_cover_state(self) -> CoverState:
        """Return a CoverState enum representing the state of the cover."""
        set_req = self.gateway.const.SetReq
        v_up = self._values.get(set_req.V_UP) == STATE_ON
        v_down = self._values.get(set_req.V_DOWN) == STATE_ON
        v_stop = self._values.get(set_req.V_STOP) == STATE_ON

        # If a V_DIMMER or V_PERCENTAGE is available, that is the amount
        # the cover is open. Otherwise, use 0 or 100 based on the V_LIGHT
        # or V_STATUS.
        amount = 100
        if set_req.V_DIMMER in self._values:
            amount = self._values[set_req.V_DIMMER]
        else:
            amount = 100 if self._values.get(set_req.V_LIGHT) == STATE_ON else 0

        if amount == 0:
            return CoverState.CLOSED
        if v_up and not v_down and not v_stop:
            return CoverState.OPENING
        if not v_up and v_down and not v_stop:
            return CoverState.CLOSING
        return CoverState.OPEN

    @property
    def is_closed(self) -> bool:
        """Return True if the cover is closed."""
        return self.get_cover_state() == CoverState.CLOSED

    @property
    def is_closing(self) -> bool:
        """Return True if the cover is closing."""
        return self.get_cover_state() == CoverState.CLOSING

    @property
    def is_opening(self) -> bool:
        """Return True if the cover is opening."""
        return self.get_cover_state() == CoverState.OPENING

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        set_req = self.gateway.const.SetReq
        return self._values.get(set_req.V_DIMMER)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the cover up."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_UP, 1, ack=1
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the cover down."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_DOWN, 1, ack=1
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_DIMMER, position, ack=1
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_STOP, 1, ack=1
        )
