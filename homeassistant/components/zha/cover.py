"""Support for ZHA covers."""
from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING, Any

from zigpy.zcl.foundation import Status

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import (
    CLUSTER_HANDLER_COVER,
    CLUSTER_HANDLER_LEVEL,
    CLUSTER_HANDLER_ON_OFF,
    CLUSTER_HANDLER_SHADE,
    DATA_ZHA,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_ATTR_UPDATED,
    SIGNAL_SET_LEVEL,
)
from .core.registries import ZHA_ENTITIES
from .entity import ZhaEntity

if TYPE_CHECKING:
    from .core.cluster_handlers import ClusterHandler
    from .core.device import ZHADevice

_LOGGER = logging.getLogger(__name__)

MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.COVER)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation cover from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.COVER]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


@MULTI_MATCH(cluster_handler_names=CLUSTER_HANDLER_COVER)
class ZhaCover(ZhaEntity, CoverEntity):
    """Representation of a ZHA cover."""

    _attr_name: str = "Cover"

    def __init__(self, unique_id, zha_device, cluster_handlers, **kwargs):
        """Init this sensor."""
        super().__init__(unique_id, zha_device, cluster_handlers, **kwargs)
        self._cover_cluster_handler = self.cluster_handlers.get(CLUSTER_HANDLER_COVER)
        self._current_position = None

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

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self.current_cover_position is None:
            return None
        return self.current_cover_position == 0

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

    @callback
    def async_set_position(self, attr_id, attr_name, value):
        """Handle position update from cluster handler."""
        _LOGGER.debug("setting position: %s", value)
        self._current_position = 100 - value
        if self._current_position == 0:
            self._state = STATE_CLOSED
        elif self._current_position == 100:
            self._state = STATE_OPEN
        self.async_write_ha_state()

    @callback
    def async_update_state(self, state):
        """Handle state update from cluster handler."""
        _LOGGER.debug("state=%s", state)
        self._state = state
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the window cover."""
        res = await self._cover_cluster_handler.up_open()
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to open cover: {res[1]}")
        self.async_update_state(STATE_OPENING)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the window cover."""
        res = await self._cover_cluster_handler.down_close()
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to close cover: {res[1]}")
        self.async_update_state(STATE_CLOSING)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the roller shutter to a specific position."""
        new_pos = kwargs[ATTR_POSITION]
        res = await self._cover_cluster_handler.go_to_lift_percentage(100 - new_pos)
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to set cover position: {res[1]}")
        self.async_update_state(
            STATE_CLOSING if new_pos < self._current_position else STATE_OPENING
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the window cover."""
        res = await self._cover_cluster_handler.stop()
        if res[1] is not Status.SUCCESS:
            raise HomeAssistantError(f"Failed to stop cover: {res[1]}")
        self._state = STATE_OPEN if self._current_position > 0 else STATE_CLOSED
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Attempt to retrieve the open/close state of the cover."""
        await super().async_update()
        await self.async_get_state()

    async def async_get_state(self, from_cache=True):
        """Fetch the current state."""
        _LOGGER.debug("polling current state")
        if self._cover_cluster_handler:
            pos = await self._cover_cluster_handler.get_attribute_value(
                "current_position_lift_percentage", from_cache=from_cache
            )
            _LOGGER.debug("read pos=%s", pos)

            if pos is not None:
                self._current_position = 100 - pos
                self._state = (
                    STATE_OPEN if self.current_cover_position > 0 else STATE_CLOSED
                )
            else:
                self._current_position = None
                self._state = None


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
    _attr_name: str = "Shade"

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

    _attr_name: str = "Keen vent"

    _attr_device_class = CoverDeviceClass.DAMPER

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
