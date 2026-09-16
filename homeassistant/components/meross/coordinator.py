"""Coordinator for Meross Bluetooth."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from meross_ble import (
    CONNECTABLE_MODELS,
    GATT_ADV_WAIT_TIMEOUT,
    MerossBLEDevice,
    MerossModel,
    parse_advertisement_data,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import ADVERTISEMENT_STALE_SECONDS, DEVICE_STARTUP_TIMEOUT
from .history import async_sync_ms120_history

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__name__)

type MerossConfigEntry = ConfigEntry[MerossBLEDataUpdateCoordinator]

# While unavailable, dump HA bluetooth-manager cache this often.
_UNAVAILABLE_ADV_PROBE_SECONDS = 10.0


def _adv_seq_from_raw_hex(raw_hex: str) -> int | None:
    """Return adv_seq (payload byte 5) from 0xBE30 service_data hex."""
    if len(raw_hex) < 12:
        return None
    try:
        return int(raw_hex[10:12], 16)
    except ValueError:
        return None


def _format_advertisement_dump(
    service_info: bluetooth.BluetoothServiceInfoBleak,
    change: bluetooth.BluetoothChange | None = None,
) -> str:
    """Compact dump of a BLE advertisement for unavailable-path logging."""
    adv = service_info.advertisement
    service_data = {
        str(key): bytes(value).hex() for key, value in (adv.service_data or {}).items()
    }
    manufacturer = {
        hex(key): bytes(value).hex()
        for key, value in (adv.manufacturer_data or {}).items()
    }
    change_part = f"change={change} " if change is not None else ""
    age = time.monotonic() - service_info.time
    raw_hex = _meross_service_data_hex(service_info)
    adv_seq = _adv_seq_from_raw_hex(raw_hex) if raw_hex else None
    seq_part = (
        f"adv_seq={adv_seq} (0x{adv_seq:02x}) " if adv_seq is not None else ""
    )
    return (
        f"{seq_part}age={age:.1f}s rssi={service_info.rssi} {change_part}"
        f"name={service_info.name!r} local_name={adv.local_name!r} "
        f"connectable={service_info.connectable} "
        f"service_uuids={list(adv.service_uuids or [])} "
        f"service_data={service_data or '(none)'} "
        f"manufacturer_data={manufacturer or '(none)'}"
    )


def _meross_service_data_hex(service_info: bluetooth.BluetoothServiceInfoBleak) -> str:
    """Return Meross service-data payload as hex (empty if missing)."""
    advertisement = service_info.advertisement
    if not advertisement.service_data:
        return ""
    for key, value in advertisement.service_data.items():
        key_l = str(key).lower().replace("-", "")
        if "be30" in key_l:
            return bytes(value).hex()
    first = next(iter(advertisement.service_data.values()), None)
    return bytes(first).hex() if first is not None else ""


class MerossBLEDataUpdateCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):
    """Subscribe to one device's advertisements."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: MerossBLEDevice,
        base_unique_id: str,
        device_name: str,
        connectable: bool,
        model: MerossModel,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=logger,
            address=ble_device.address,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=connectable,
        )
        self.ble_device = ble_device
        self.device = device
        self.device_name = device_name
        self.base_unique_id = base_unique_id
        self.model = model
        self.config_entry = config_entry
        self._ready_event = asyncio.Event()
        self._was_unavailable = True
        self._history_lock = asyncio.Lock()
        self._history_task: asyncio.Task[None] | None = None
        self._history_yield_unsub: CALLBACK_TYPE | None = None
        self.history_force_full_resync = False
        self.last_new_events: list[tuple[int, int]] = []
        self._stale_unsub: CALLBACK_TYPE | None = None
        self._unavailable_probe_unsub: CALLBACK_TYPE | None = None
        self._last_parseable_monotonic: float | None = None
        self._adv_waiters: list[asyncio.Event] = []
        _LOGGER.debug(
            "%s: %s BLE stale watchdog=%ss",
            ble_device.address,
            model.value.upper(),
            ADVERTISEMENT_STALE_SECONDS,
        )

    @callback
    def _async_notify_advertisement_waiters(self) -> None:
        for event in self._adv_waiters:
            event.set()

    async def async_wait_next_advertisement(
        self, timeout: float = GATT_ADV_WAIT_TIMEOUT
    ) -> bool:
        """Wait until the next parseable advertisement for this device."""
        event = asyncio.Event()
        self._adv_waiters.append(event)
        try:
            async with asyncio.timeout(timeout):
                await event.wait()
            return True
        except TimeoutError:
            return False
        finally:
            self._adv_waiters.remove(event)

    @callback
    def _async_cancel_stale_timer(self) -> None:
        if self._stale_unsub is not None:
            self._stale_unsub()
            self._stale_unsub = None

    @callback
    def _async_cancel_unavailable_adv_probe(self) -> None:
        if self._unavailable_probe_unsub is not None:
            self._unavailable_probe_unsub()
            self._unavailable_probe_unsub = None

    @callback
    def _async_log_bluetooth_manager_advertisement(self, reason: str) -> None:
        """Dump HA scanner cache — fires even when no advertisement callback arrives."""
        parseable_age = (
            time.monotonic() - self._last_parseable_monotonic
            if self._last_parseable_monotonic is not None
            else None
        )
        parseable_txt = (
            f"{parseable_age:.1f}s" if parseable_age is not None else "never"
        )
        service_info = bluetooth.async_last_service_info(
            self.hass, self.address, connectable=False
        )
        if service_info is None:
            _LOGGER.debug(
                "%s: %s bluetooth manager has no advertisement "
                "(%s; last parseable=%s)",
                self.address,
                self.model.value.upper(),
                reason,
                parseable_txt,
            )
            return
        _LOGGER.debug(
            "%s: %s bluetooth manager advertisement "
            "(%s; last parseable=%s) %s",
            self.address,
            self.model.value.upper(),
            reason,
            parseable_txt,
            _format_advertisement_dump(service_info),
        )

    @callback
    def _async_schedule_unavailable_adv_probe(self) -> None:
        self._async_cancel_unavailable_adv_probe()
        self._unavailable_probe_unsub = async_call_later(
            self.hass,
            _UNAVAILABLE_ADV_PROBE_SECONDS,
            self._async_unavailable_adv_probe,
        )

    @callback
    def _async_unavailable_adv_probe(self, _now: datetime) -> None:
        """Poll scanner cache while the device stays unavailable."""
        self._unavailable_probe_unsub = None
        if not self._was_unavailable and self.available:
            return
        self._async_log_bluetooth_manager_advertisement("still unavailable")
        self._async_schedule_unavailable_adv_probe()

    @callback
    def _async_schedule_stale_timer(self) -> None:
        """Restart watchdog after a parseable advertisement."""
        self._async_cancel_stale_timer()
        self._stale_unsub = async_call_later(
            self.hass,
            ADVERTISEMENT_STALE_SECONDS,
            self._async_advertisement_stale,
        )

    @callback
    def _async_advertisement_stale(self, _now: datetime) -> None:
        """Force unavailable when advertisements stop (macOS Bleak cache workaround)."""
        self._stale_unsub = None
        if not self.available:
            return
        self._available = False
        self._was_unavailable = True
        _LOGGER.info(
            "%s: %s no parseable BLE advertisement for %ss → marking unavailable",
            self.address,
            self.model.value.upper(),
            ADVERTISEMENT_STALE_SECONDS,
        )
        self._async_log_bluetooth_manager_advertisement("marking unavailable")
        self._async_schedule_unavailable_adv_probe()
        self.async_update_listeners()

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        return (
            self.hass.state is CoreState.running
            and self.connectable
            and self.device.poll_needed(seconds_since_last_poll)
            and bool(
                bluetooth.async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_update(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        await self.device.update()

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        # HA's async_track_unavailable (~30s) fires on missed scans even when
        # firmware is still advertising. Ignore it; offline is decided only by
        # the stale timer after parseable advertisements stop.
        self._last_name = service_info.name
        _LOGGER.debug(
            "%s: HA bluetooth reported unavailable for %s "
            "(ignored; offline after %ss without ads)",
            self.address,
            self.device_name,
            ADVERTISEMENT_STALE_SECONDS,
        )

    @callback
    def _async_stop(self) -> None:
        self._async_cancel_stale_timer()
        self._async_cancel_unavailable_adv_probe()
        self._async_cancel_history_yield_timer()
        super()._async_stop()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        self.ble_device = service_info.device
        self.device.update_ble_device(service_info.device)
        recovered = self._was_unavailable or not self.available
        raw_hex = _meross_service_data_hex(service_info) or "(none)"
        path = "after unavailable" if recovered else "online"

        _LOGGER.debug(
            "%s: %s advertisement (%s) %s",
            service_info.address,
            self.model.value.upper(),
            path,
            _format_advertisement_dump(service_info, change),
        )

        adv = parse_advertisement_data(
            service_info.device, service_info.advertisement, self.model
        )
        if not adv or "status" not in adv.data:
            _LOGGER.debug(
                "%s: %s advertisement (%s) could not be parsed "
                "(no 0xBE30 status; service_data=%s)",
                service_info.address,
                self.model.value.upper(),
                path,
                raw_hex,
            )
            return
        new_events = self.device.update_from_advertisement(adv)
        self._ready_event.set()
        # Firmware advertises on a fixed interval even when state is unchanged.
        self._last_parseable_monotonic = time.monotonic()
        self._async_schedule_stale_timer()
        self._async_notify_advertisement_waiters()
        self.last_new_events = new_events
        if recovered:
            self._was_unavailable = False
            self._async_cancel_unavailable_adv_probe()
        super()._async_handle_bluetooth_event(service_info, change)

    @callback
    def _async_cancel_history_yield_timer(self) -> None:
        if self._history_yield_unsub is not None:
            self._history_yield_unsub()
            self._history_yield_unsub = None

    @callback
    def async_schedule_history_sync(self) -> None:
        """Schedule MS120 local history import (setup / reload only)."""
        if self.model is not MerossModel.MS120:
            return
        self._async_cancel_history_yield_timer()
        if self._history_task and not self._history_task.done():
            _LOGGER.debug(
                "%s: history sync already running, skip schedule",
                self.ble_device.address,
            )
            return

        _LOGGER.debug(
            "%s: scheduling MS120 history sync task",
            self.ble_device.address,
        )

        async def _run() -> None:
            async with self._history_lock:
                await async_sync_ms120_history(self.hass, self)

        self._history_task = self.hass.async_create_task(
            _run(), name=f"meross_ble_history_{self.base_unique_id}"
        )

    async def async_wait_ready(self) -> bool:
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(DEVICE_STARTUP_TIMEOUT):
                await self._ready_event.wait()
            return True
        return False

    def model_is_connectable(self) -> bool:
        return self.model in CONNECTABLE_MODELS
