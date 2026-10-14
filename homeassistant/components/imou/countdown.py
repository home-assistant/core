"""Local remaining-time clock for the plug countdown number."""

from collections.abc import Callable
from datetime import datetime, timedelta
from math import ceil
from typing import TYPE_CHECKING

from pyimouapi.const import PARAM_STATE
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import PARAM_COUNT_DOWN_SWITCH, imou_device_identifier

if TYPE_CHECKING:
    from .coordinator import ImouDataUpdateCoordinator

_TICK = timedelta(minutes=1)


def parse_countdown_minutes(device: ImouHaDevice) -> int:
    """Return the device's countdown minutes, or 0 when missing/invalid."""
    raw = device.texts.get(PARAM_COUNT_DOWN_SWITCH, {}).get(PARAM_STATE, "0")
    try:
        return max(0, int(raw))
    except TypeError, ValueError:
        return 0


class CountdownTracker:
    """Count remaining minutes locally so the number still moves without a poll."""

    def __init__(self) -> None:
        """Initialize empty tracking state."""
        self._ends: dict[str, datetime] = {}
        self._expire_unsub: dict[str, Callable[[], None]] = {}
        self._tick_unsub: Callable[[], None] | None = None

    def remaining_minutes(self, device_key: str) -> int:
        """Return whole minutes left, rounding up so 1s still shows as 1."""
        end = self._ends.get(device_key)
        if end is None:
            return 0
        secs = (end - dt_util.utcnow()).total_seconds()
        if secs <= 0:
            return 0
        return ceil(secs / 60)

    def ends_at(self, device_key: str) -> datetime | None:
        """Return the local end time, if a countdown is running."""
        return self._ends.get(device_key)

    def start_minutes(
        self,
        hass: HomeAssistant,
        coordinator: ImouDataUpdateCoordinator,
        device_key: str,
        minutes: int,
    ) -> None:
        """Start, replace, or cancel the local clock for one device."""
        self._cancel_expire(device_key)
        if minutes <= 0:
            self._ends.pop(device_key, None)
            self._maybe_stop_tick()
            return
        self._arm(
            hass,
            coordinator,
            device_key,
            dt_util.utcnow() + timedelta(minutes=minutes),
        )

    def seed_if_idle(
        self,
        hass: HomeAssistant,
        coordinator: ImouDataUpdateCoordinator,
        device: ImouHaDevice,
    ) -> None:
        """Start from the device value when Home Assistant has no local clock yet."""
        device_key = imou_device_identifier(device)
        if device_key in self._ends:
            return
        minutes = parse_countdown_minutes(device)
        if minutes:
            self.start_minutes(hass, coordinator, device_key, minutes)

    def sync_from_device(
        self,
        hass: HomeAssistant,
        coordinator: ImouDataUpdateCoordinator,
        device: ImouHaDevice,
    ) -> None:
        """Replace the local clock with remaining minutes from a cloud refresh."""
        self.start_minutes(
            hass,
            coordinator,
            imou_device_identifier(device),
            parse_countdown_minutes(device),
        )

    def sync_all(
        self, hass: HomeAssistant, coordinator: ImouDataUpdateCoordinator
    ) -> None:
        """Resync every plug that exposes a countdown after a status poll."""
        for device in coordinator.devices:
            if PARAM_COUNT_DOWN_SWITCH in device.texts:
                self.sync_from_device(hass, coordinator, device)

    def async_unload(self) -> None:
        """Drop every timer when the config entry unloads."""
        for unsub in list(self._expire_unsub.values()):
            unsub()
        self._expire_unsub.clear()
        self._ends.clear()
        self._maybe_stop_tick()

    def _arm(
        self,
        hass: HomeAssistant,
        coordinator: ImouDataUpdateCoordinator,
        device_key: str,
        end: datetime,
    ) -> None:
        self._ends[device_key] = end

        @callback
        def _expire(_now: datetime) -> None:
            self._expire_unsub.pop(device_key, None)
            self._ends.pop(device_key, None)
            device = coordinator.get_device(device_key)
            if device is not None and PARAM_COUNT_DOWN_SWITCH in device.texts:
                device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] = "0"
            self._maybe_stop_tick()
            coordinator.async_update_listeners()

        self._expire_unsub[device_key] = async_track_point_in_utc_time(
            hass, _expire, end
        )
        self._ensure_tick(hass, coordinator)

    def _ensure_tick(
        self, hass: HomeAssistant, coordinator: ImouDataUpdateCoordinator
    ) -> None:
        if self._tick_unsub is not None:
            return

        @callback
        def _tick(_now: datetime) -> None:
            coordinator.async_update_listeners()

        self._tick_unsub = async_track_time_interval(hass, _tick, _TICK)

    def _maybe_stop_tick(self) -> None:
        if self._ends:
            return
        if self._tick_unsub is not None:
            self._tick_unsub()
            self._tick_unsub = None

    def _cancel_expire(self, device_key: str) -> None:
        unsub = self._expire_unsub.pop(device_key, None)
        if unsub is not None:
            unsub()
