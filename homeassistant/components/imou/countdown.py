"""Local end-time tracking for the plug countdown datetime."""

from collections.abc import Callable
from datetime import datetime, timedelta
from math import ceil
from typing import TYPE_CHECKING

from pyimouapi.const import PARAM_STATE, PARAM_STATUS
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import PARAM_COUNT_DOWN_SWITCH, imou_device_identifier

if TYPE_CHECKING:
    from .coordinator import ImouDataUpdateCoordinator


def parse_countdown_minutes(device: ImouHaDevice) -> int:
    """Return the device's countdown minutes, or 0 when missing/invalid."""
    raw = device.texts.get(PARAM_COUNT_DOWN_SWITCH, {}).get(PARAM_STATE, "0")
    try:
        return max(0, int(raw))
    except TypeError, ValueError:
        return 0


def minutes_until(value: datetime, *, now: datetime | None = None) -> int:
    """Return whole minutes from now until value (0 when not in the future)."""
    current = now or dt_util.utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    secs = (value - current).total_seconds()
    if secs <= 0:
        return 0
    return ceil(secs / 60)


class CountdownTracker:
    """Remember when each plug's countdown ends.

    The datetime entity exposes that end time. Home Assistant does not rewrite
    state every minute; the UI can show remaining time from the timestamp.
    """

    def __init__(self) -> None:
        """Initialize empty tracking state."""
        self._ends: dict[str, datetime] = {}
        self._expire_unsub: dict[str, Callable[[], None]] = {}

    def ends_at(self, device_key: str) -> datetime | None:
        """Return the local end time, if a countdown is running."""
        return self._ends.get(device_key)

    def remaining_minutes(self, device_key: str, *, now: datetime | None = None) -> int:
        """Return whole minutes left for a local end, rounding up."""
        end = self._ends.get(device_key)
        if end is None:
            return 0
        current = now or dt_util.utcnow()
        secs = (end - current).total_seconds()
        if secs <= 0:
            return 0
        return ceil(secs / 60)

    def start_minutes(
        self,
        hass: HomeAssistant,
        coordinator: ImouDataUpdateCoordinator,
        device_key: str,
        minutes: int,
    ) -> None:
        """Start, replace, or cancel the local end time for one device."""
        self._cancel_expire(device_key)
        if minutes <= 0:
            self._ends.pop(device_key, None)
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
        """Start from the device value when Home Assistant has no local end yet."""
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
        """Align the local end with the cloud, without jittering unchanged timers."""
        status = device.sensors.get(PARAM_STATUS, {}).get(PARAM_STATE)
        if status == DeviceStatus.OFFLINE.value:
            # Offline refreshes keep the last countdown text; do not reset the end.
            return
        device_key = imou_device_identifier(device)
        minutes = parse_countdown_minutes(device)
        if minutes <= 0:
            self.start_minutes(hass, coordinator, device_key, 0)
            return
        # Cloud only reports whole minutes. Keep the existing end when the
        # remaining minute count still matches so polls do not shift the deadline.
        if device_key in self._ends and self.remaining_minutes(device_key) == minutes:
            return
        self.start_minutes(hass, coordinator, device_key, minutes)

    def sync_all(
        self, hass: HomeAssistant, coordinator: ImouDataUpdateCoordinator
    ) -> None:
        """Resync every plug that exposes a countdown after a status poll."""
        for device in coordinator.devices:
            if PARAM_COUNT_DOWN_SWITCH in device.texts:
                self.sync_from_device(hass, coordinator, device)

    def cancel_device(self, device_key: str) -> None:
        """Drop the local end for a device that left the account."""
        self._cancel_expire(device_key)
        self._ends.pop(device_key, None)

    def async_unload(self) -> None:
        """Drop every timer when the config entry unloads."""
        for unsub in list(self._expire_unsub.values()):
            unsub()
        self._expire_unsub.clear()
        self._ends.clear()

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
            coordinator.async_update_listeners()

        self._expire_unsub[device_key] = async_track_point_in_utc_time(
            hass, _expire, end
        )

    def _cancel_expire(self, device_key: str) -> None:
        unsub = self._expire_unsub.pop(device_key, None)
        if unsub is not None:
            unsub()
