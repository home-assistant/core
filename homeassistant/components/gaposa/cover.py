"""Gaposa cover entity."""

from datetime import datetime, timedelta
import logging
from typing import Any, override

from pygaposa import Motor

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
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
    """Add a cover entity for every motor present at the first refresh.

    Motors added to the Gaposa account later will not appear until the
    config entry is reloaded — the ``dynamic-devices`` quality-scale rule
    is still ``todo`` for this integration.
    """
    coordinator = config_entry.runtime_data
    async_add_entities(
        GaposaCover(coordinator, motor_id, motor)
        for motor_id, motor in coordinator.data.items()
    )


class GaposaCover(CoordinatorEntity[DataUpdateCoordinatorGaposa], CoverEntity):
    """A single Gaposa motor exposed as a cover entity."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = _SUPPORTED_FEATURES
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: DataUpdateCoordinatorGaposa,
        motor_id: str,
        motor: Motor,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator, context=motor_id)
        self._motor_id = motor_id
        self._motor = motor
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
    def motor(self) -> Motor:
        """Return the current Motor object from coordinator data.

        Falls back to the initial Motor instance if the motor has
        disappeared from a refresh — property callers on an
        unavailable entity (e.g. logging in async_write_ha_state)
        should not raise KeyError.
        """
        return self.coordinator.data.get(self._motor_id, self._motor)

    @property
    @override
    def available(self) -> bool:
        """Entity is available while the motor is known to the coordinator."""
        return super().available and self._motor_id in self.coordinator.data

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending motion-window refresh on removal."""
        await super().async_will_remove_from_hass()
        if self._cancel_motion_refresh is not None:
            self._cancel_motion_refresh()
            self._cancel_motion_refresh = None

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return whether the cover is fully closed."""
        # stop() returns before pygaposa's post-command poll updates
        # motor.state, so trusting the stale UP/DOWN would report the
        # pre-stop endpoint even though the cover was halted mid-way.
        # Report unknown until the state converges or MOTION_DELAY
        # elapses.
        if self._is_post_stop_pending():
            return None
        if self.motor.state == STATE_DOWN:
            return True
        if self.motor.state == STATE_UP:
            return False
        return None

    @property
    @override
    def is_opening(self) -> bool:
        """Return whether the cover is opening right now."""
        return self._is_moving() and self._last_command == COMMAND_UP

    @property
    @override
    def is_closing(self) -> bool:
        """Return whether the cover is closing right now."""
        return self._is_moving() and self._last_command == COMMAND_DOWN

    def _is_moving(self) -> bool:
        """True while we're still inside the motion window of the last command."""
        if self._last_command_time is None or self._last_command == COMMAND_STOP:
            return False
        deadline = self._last_command_time + timedelta(seconds=MOTION_DELAY)
        return dt_util.utcnow() < deadline

    def _is_post_stop_pending(self) -> bool:
        """True while we're waiting for motor.state to reflect a stop command."""
        if self._last_command != COMMAND_STOP or self._last_command_time is None:
            return False
        deadline = self._last_command_time + timedelta(seconds=MOTION_DELAY)
        return dt_util.utcnow() < deadline

    def _begin_motion(self, command: str) -> None:
        """Record an open/close command and arm the motion-window timer."""
        self._last_command = command
        self._last_command_time = dt_util.utcnow()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.motor.up(False)
        # Trigger the motion window unless the cover is already at
        # the top and idle. Reversing mid-close needs a fresh motion
        # window too — pygaposa may not have polled since the last
        # command, so motor.state can still read UP while the cover
        # is physically moving down.
        if self.motor.state != STATE_UP or self.is_closing:
            self._begin_motion(COMMAND_UP)
            self._schedule_refresh_after_motion()
        self.async_write_ha_state()

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.motor.down(False)
        if self.motor.state != STATE_DOWN or self.is_opening:
            self._begin_motion(COMMAND_DOWN)
            self._schedule_refresh_after_motion()
        self.async_write_ha_state()

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover.

        Await motor.stop() before collapsing the local motion window
        so a failed command leaves the cover still reporting as
        moving rather than falsely stopped.
        """
        await self.motor.stop(False)
        self._last_command = COMMAND_STOP
        # Timestamp arms _is_post_stop_pending so is_closed reports
        # unknown until the post-command poll updates motor.state.
        self._last_command_time = dt_util.utcnow()
        if self._cancel_motion_refresh is not None:
            self._cancel_motion_refresh()
            self._cancel_motion_refresh = None
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
        self._schedule_refresh_after_motion()

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
