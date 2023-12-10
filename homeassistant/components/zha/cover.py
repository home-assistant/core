"""Support for ZHA covers."""
from __future__ import annotations

import asyncio
import collections
import functools
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from zigpy.zcl.foundation import Status

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_COVER,
    CLUSTER_HANDLER_LEVEL,
    CLUSTER_HANDLER_ON_OFF,
    CLUSTER_HANDLER_SHADE,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_SET_LEVEL,
)
from .core.helpers import get_zha_data
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.COVER)

MOVEMENT_TIMEOUT = timedelta(seconds=2)
"""If no update is received from cover for X seconds, the movement is considered stopped."""

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation cover from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.COVER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


_PositionHistoryRecord = collections.namedtuple("_PositionHistoryRecord", ["datetime", "lift", "tilt"])


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_COVER)
class ZhaCover(ZhaEntity, CoverEntity):
    """
    Representation of a ZHA cover.
    
    Covers doesn't have a way to report movement, they are only reporting changes in lift / tilt.
    That's why we track history of these reports and judge the (lack of) movement + direction based on that.
    """

    _attr_translation_key: str = "cover"

    def __init__(self, unique_id, zha_device, cluster_handlers, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cover_cluster_handler = self.cluster_handlers.get(CLUSTER_HANDLER_COVER)
        self._current_position = None
        self._tilt_position = None
        self._position_history = collections.deque(maxlen=2)
        self._cancel_clear_movement_timer = None

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._cover_cluster_handler, SIGNAL_ATTR_UPDATED, self.async_set_position
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._state = last_state.state
        if "current_position" in last_state.attributes:
            self._current_position = last_state.attributes["current_position"]
        if "current_tilt_position" in last_state.attributes:
            self._tilt_position = last_state.attributes[
                "current_tilt_position"
            ]  # first allocation activate tilt

    @property
    def is_closed(self) -> bool | None:
        """
        Return if the cover is closed.
        
        Consider cover closed only if both tilt and lift are 0.
        If cover doesn't support tilt, only care about lift.
        """
        if self._current_position is None:
            return None
        return self._current_position == 0 and getattr(self, "_tilt_position", 0) == 0

    @property
    def _is_open(self) -> bool | None:
        """
        Return if the cover is open.
        
        Consider cover closed only if both tilt and lift are 100.
        If cover doesn't support tilt, only care about lift.

        This is not required by the API, but it is only used internally.
        """
        if self._current_position is None:
            return None
        return self._current_position == 100 and getattr(self, "_tilt_position", 100) == 100

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._state == STATE_OPENING

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._state == STATE_CLOSING

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of ZHA cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._current_position

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position of the cover."""
        return self._tilt_position

    @callback
    def async_set_position(self, attr_id, attr_name, value):
        """Handle position update from cluster handler."""
        if attr_name == "current_position_lift_percentage":
            self._current_position = 100 - value
        elif attr_name == "current_position_tilt_percentage":
            self._tilt_position = 100 - value
        self._touch_position()
        if self.is_closed:
            self._async_update_state(STATE_CLOSED)
        elif self._is_open:
            self._async_update_state(STATE_OPEN)
        else:
            # somewhere in between fully closed and fully open
            # TODO handle external updates by looking at position history trend
            self._async_update_state()

    def _touch_position(self):
        """Store current timestamp, lift and tilt into position history."""
        self._position_history.append(_PositionHistoryRecord(datetime.now(), self._current_position, self._tilt_position))

    @callback
    def _clear_movement(self, _=None):
        """Clear the moving status of the cover if there is no recent update."""
        self.debug("No movement reported for %s", MOVEMENT_TIMEOUT)
        self._async_update_state(STATE_CLOSED if self.is_closed else STATE_OPEN)
        self._cancel_clear_movement_timer = None

    @callback
    def _async_update_state(self, state=None):
        """
        Inform HASS of current state.
        
        In case of opening/closing states, schedule a timer to clear movement.
        """
        if state:
            self.debug("Setting state: %s", state)
            self._state = state
        self.async_write_ha_state()
        if self._state in (STATE_OPENING, STATE_CLOSING):
            if self._cancel_clear_movement_timer:
                self._cancel_clear_movement_timer()
            self._cancel_clear_movement_timer = async_call_later(self.hass, MOVEMENT_TIMEOUT, self._clear_movement)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the window cover."""
        self._touch_position()
        res = await self._cover_cluster_handler.up_open()
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to open cover: {res[1]}")
        self._async_update_state(STATE_OPENING)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        self._touch_position()
        res = await self._cover_cluster_handler.go_to_tilt_percentage(0)
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to open cover tilt: {res[1]}")
        self._async_update_state(STATE_OPENING)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the window cover."""
        self._touch_position()
        res = await self._cover_cluster_handler.down_close()
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to close cover: {res[1]}")
        self._async_update_state(STATE_CLOSING)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        self._touch_position()
        res = await self._cover_cluster_handler.go_to_tilt_percentage(100)
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to close cover tilt: {res[1]}")
        self._async_update_state(STATE_CLOSING)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the roller shutter to a specific position."""
        self._touch_position()
        new_pos = kwargs[ATTR_POSITION]
        res = await self._cover_cluster_handler.go_to_lift_percentage(100 - new_pos)
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to set cover position: {res[1]}")
        self._async_update_state(
            STATE_CLOSING if new_pos < self._current_position else STATE_OPENING
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover til to a specific position."""
        self._touch_position()
        new_pos = kwargs[ATTR_TILT_POSITION]
        res = await self._cover_cluster_handler.go_to_tilt_percentage(100 - new_pos)
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to set cover tilt position: {res[1]}")
        self._async_update_state(
            STATE_CLOSING if new_pos < self._tilt_position else STATE_OPENING
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the window cover."""
        self._touch_position()
        res = await self._cover_cluster_handler.stop()
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to stop cover: {res[1]}")
        self._async_update_state(STATE_CLOSED if self.is_closed else STATE_OPEN)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self.async_stop_cover()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the movement timer when entity is removed."""
        if self._cancel_clear_movement_timer:
            self._cancel_clear_movement_timer()
        await super().async_will_remove_from_hass()


@MULTI_MATCH(
    cluster_handler_names={
        CLUSTER_HANDLER_LEVEL,
        CLUSTER_HANDLER_ON_OFF,
        CLUSTER_HANDLER_SHADE,
    }
)
class Shade(ZhaEntity, CoverEntity):
    """ZHA Shade."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_translation_key: str = "shade"

    def __init__(
        self,
        unique_id: str,
        zha_device: ZHADevice,
        cluster_handlers: list[ClusterHandler],
        **kwargs,
    ) -> None:
        """Initialize the ZHA light."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._on_off_cluster_handler = self.cluster_handlers[CLUSTER_HANDLER_ON_OFF]
        self._level_cluster_handler = self.cluster_handlers[CLUSTER_HANDLER_LEVEL]
        self._position: int | None = None
        self._is_open: bool | None = None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def is_closed(self) -> bool | None:
        """Return True if shade is closed."""
        if self._is_open is None:
            return None
        return not self._is_open

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        await super().async_added_to_hass()
        self.async_accept_signal(
            self._on_off_cluster_handler,
            SIGNAL_ATTR_UPDATED,
            self.async_set_open_closed,
        )
        self.async_accept_signal(
            self._level_cluster_handler, SIGNAL_SET_LEVEL, self.async_set_level
        )

    @callback
    def async_restore_last_state(self, last_state):
        """Restore previous state."""
        self._is_open = last_state.state == STATE_OPEN
        if ATTR_CURRENT_POSITION in last_state.attributes:
            self._position = last_state.attributes[ATTR_CURRENT_POSITION]

    @callback
    def async_set_open_closed(self, attr_id: int, attr_name: str, value: bool) -> None:
        """Set open/closed state."""
        self._is_open = bool(value)
        self.async_write_ha_state()

    @callback
    def async_set_level(self, value: int) -> None:
        """Set the reported position."""
        value = max(0, min(255, value))
        self._position = int(value * 100 / 255)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the window cover."""
        res = await self._on_off_cluster_handler.on()
        if res[1] != Status.SUCCESS:
            raise HomeAssistantError(f"Failed to open cover: {res[1]}")

        self._is_open = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the window cover."""
        res = await self._on_off_cluster_handler.off()
        if res[1] != Status.SUCCESS:
            raise HomeAssistantError(f"Failed to close cover: {res[1]}")

        self._is_open = False
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the roller shutter to a specific position."""
        new_pos = kwargs[ATTR_POSITION]
        res = await self._level_cluster_handler.move_to_level_with_on_off(
            new_pos * 255 / 100, 1
        )

        if res[1] != Status.SUCCESS:
            raise HomeAssistantError(f"Failed to set cover position: {res[1]}")

        self._position = new_pos
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        res = await self._level_cluster_handler.stop()
        if res[1] != Status.SUCCESS:
            raise HomeAssistantError(f"Failed to stop cover: {res[1]}")


@MULTI_MATCH(
    cluster_handler_names={CLUSTER_HANDLER_LEVEL, CLUSTER_HANDLER_ON_OFF},
    manufacturers="Keen Home Inc",
)
class KeenVent(Shade):
    """Keen vent cover."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_translation_key: str = "keen_vent"

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        position = self._position or 100
        await asyncio.gather(
            self._level_cluster_handler.move_to_level_with_on_off(
                position * 255 / 100, 1
            ),
            self._on_off_cluster_handler.on(),
        )

        self._is_open = True
        self._position = position
        self.async_write_ha_state()
