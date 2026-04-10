"""Gaposa cover entity."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from pygaposa import Motor

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GaposaConfigEntry
from .const import (
    COMMAND_DOWN,
    COMMAND_STOP,
    COMMAND_UP,
    DOMAIN,
    MOTION_DELAY,
    STATE_DOWN,
    STATE_UP,
)
from .coordinator import DataUpdateCoordinatorGaposa

_LOGGER = logging.getLogger(__name__)

_SUPPORTED_FEATURES = (
    CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GaposaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a cover entity for every motor the coordinator knows about."""
    coordinator = config_entry.runtime_data
    known_entities: dict[str, GaposaCover] = {}

    @callback
    def _async_add_remove_entities() -> None:
        """Add new motors and drop covers for motors that have disappeared."""
        latest_ids = set(coordinator.data)
        new_entities: list[GaposaCover] = []

        for motor_id, motor in coordinator.data.items():
            if motor_id not in known_entities:
                entity = GaposaCover(coordinator, motor_id, motor)
                new_entities.append(entity)
                known_entities[motor_id] = entity

        if new_entities:
            async_add_entities(new_entities)

        for motor_id in list(known_entities):
            if motor_id not in latest_ids:
                stale = known_entities.pop(motor_id)
                hass.async_create_task(stale.async_remove())

    _async_add_remove_entities()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_remove_entities)
    )


class GaposaCover(CoordinatorEntity[DataUpdateCoordinatorGaposa], CoverEntity):
    """A single Gaposa motor exposed as a cover entity."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = _SUPPORTED_FEATURES
    _attr_has_entity_name = True
    _attr_name = None  # The device name is the motor name; don't double it.

    def __init__(
        self,
        coordinator: DataUpdateCoordinatorGaposa,
        motor_id: str,
        motor: Motor,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator, context=motor_id)
        self._motor_id = motor_id
        self.motor = motor
        self._last_command: str | None = None
        self._last_command_time: datetime | None = None
        self._attr_unique_id = motor_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, motor_id)},
            name=motor.name,
            manufacturer="Gaposa",
        )
        self._motion_task: asyncio.Task[None] | None = None

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending motion-window refresh task on removal."""
        await super().async_will_remove_from_hass()
        if self._motion_task is not None and not self._motion_task.done():
            self._motion_task.cancel()

    @property
    def is_open(self) -> bool | None:
        """Return whether the cover is fully open."""
        if self.motor.state == STATE_UP:
            return True
        if self.motor.state == STATE_DOWN:
            return False
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is fully closed."""
        if self.motor.state == STATE_DOWN:
            return True
        if self.motor.state == STATE_UP:
            return False
        return None

    @property
    def is_opening(self) -> bool:
        """Return whether the cover is opening right now."""
        return self._is_moving() and self._last_command == COMMAND_UP

    @property
    def is_closing(self) -> bool:
        """Return whether the cover is closing right now."""
        return self._is_moving() and self._last_command == COMMAND_DOWN

    def _is_moving(self) -> bool:
        """True while we're still inside the motion window of the last command."""
        if self._last_command_time is None or self._last_command == COMMAND_STOP:
            return False
        deadline = self._last_command_time + timedelta(seconds=MOTION_DELAY)
        return dt_util.utcnow() < deadline

    def _begin_motion(self, command: str) -> None:
        """Record an open/close command and arm the motion-window timer."""
        self._last_command = command
        self._last_command_time = dt_util.utcnow()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._begin_motion(COMMAND_UP)
        await self.motor.up(False)
        self.async_write_ha_state()
        self._schedule_refresh_after_motion()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._begin_motion(COMMAND_DOWN)
        await self.motor.down(False)
        self.async_write_ha_state()
        self._schedule_refresh_after_motion()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover and collapse the motion window immediately."""
        self._last_command = COMMAND_STOP
        self._last_command_time = None
        await self.motor.stop(True)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    def _schedule_refresh_after_motion(self) -> None:
        """Start (or replace) a background task that refreshes once motion ends."""
        if self._motion_task is not None and not self._motion_task.done():
            self._motion_task.cancel()
        self._motion_task = self.hass.async_create_task(self._refresh_after_motion())

    async def _refresh_after_motion(self) -> None:
        """Wait for the motion window to close, then ask the coordinator to refresh."""
        try:
            await asyncio.sleep(MOTION_DELAY)
        except asyncio.CancelledError:
            return
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
