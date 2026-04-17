"""Gaposa cover entity."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from pygaposa import Motor

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
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

        entity_registry = er.async_get(hass)
        for motor_id in list(known_entities):
            if motor_id not in latest_ids:
                stale = known_entities.pop(motor_id)
                # stale.async_remove() only drops the runtime state but
                # leaves the entity_registry entry (and the associated
                # device) behind. For a motor that has been removed from
                # the Gaposa account, fully remove the registry entry so
                # it doesn't linger as an orphan.
                if stale.entity_id:
                    entity_registry.async_remove(stale.entity_id)
                else:
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
        """Initialize the cover.

        Only ``motor_id`` is stored as persistent state on the entity; the
        current ``Motor`` object is resolved from ``coordinator.data`` on
        each access so entity state can't desync from the library if
        pygaposa ever starts returning fresh instances on refresh.
        """
        super().__init__(coordinator, context=motor_id)
        self._motor_id = motor_id
        self._last_command: str | None = None
        self._last_command_time: datetime | None = None
        self._attr_unique_id = motor_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, motor_id)},
            name=motor.name,
            manufacturer="Gaposa",
        )
        self._cancel_motion_refresh: CALLBACK_TYPE | None = None

    @property
    def motor(self) -> Motor | None:
        """Return the current Motor object, or ``None`` if it has been removed."""
        return self.coordinator.data.get(self._motor_id)

    @property
    def available(self) -> bool:
        """Entity is available while the motor is still known to the coordinator."""
        return super().available and self.motor is not None

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending motion-window refresh on removal."""
        await super().async_will_remove_from_hass()
        if self._cancel_motion_refresh is not None:
            self._cancel_motion_refresh()
            self._cancel_motion_refresh = None

    @property
    def is_open(self) -> bool | None:
        """Return whether the cover is fully open."""
        motor = self.motor
        if motor is None:
            return None
        if motor.state == STATE_UP:
            return True
        if motor.state == STATE_DOWN:
            return False
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return whether the cover is fully closed."""
        motor = self.motor
        if motor is None:
            return None
        if motor.state == STATE_DOWN:
            return True
        if motor.state == STATE_UP:
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
        motor = self.motor
        if motor is None:
            return
        self._begin_motion(COMMAND_UP)
        await motor.up(False)
        self.async_write_ha_state()
        self._schedule_refresh_after_motion()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        motor = self.motor
        if motor is None:
            return
        self._begin_motion(COMMAND_DOWN)
        await motor.down(False)
        self.async_write_ha_state()
        self._schedule_refresh_after_motion()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover and collapse the motion window immediately."""
        self._last_command = COMMAND_STOP
        self._last_command_time = None
        if self._cancel_motion_refresh is not None:
            self._cancel_motion_refresh()
            self._cancel_motion_refresh = None
        motor = self.motor
        if motor is None:
            return
        await motor.stop(True)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @callback
    def _schedule_refresh_after_motion(self) -> None:
        """Schedule a coordinator refresh once the motion window expires."""
        if self._cancel_motion_refresh is not None:
            self._cancel_motion_refresh()
        self._cancel_motion_refresh = async_call_later(
            self.hass, MOTION_DELAY, self._on_motion_complete
        )

    async def _on_motion_complete(self, _now: datetime) -> None:
        """Coordinator refresh after the cover has finished moving."""
        self._cancel_motion_refresh = None
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
