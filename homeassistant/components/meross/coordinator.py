"""Coordinator for Meross Bluetooth."""

import asyncio
import contextlib
from datetime import datetime
from typing import TYPE_CHECKING, override

from meross_ble import (
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
from homeassistant.const import CONF_MODEL
from homeassistant.core import CALLBACK_TYPE, CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import ADVERTISEMENT_STALE_SECONDS, DEVICE_STARTUP_TIMEOUT, LOGGER

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

type MerossConfigEntry = ConfigEntry[MerossBLEDataUpdateCoordinator]


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
        config_entry: MerossConfigEntry,
        ble_device: BLEDevice,
        device: MerossBLEDevice,
    ) -> None:
        """Initialize Meross BLE data updater."""
        assert config_entry.unique_id is not None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            address=ble_device.address,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            # False = receive connectable and non-connectable advertisements.
            connectable=False,
        )
        self.config_entry = config_entry
        self.ble_device = ble_device
        self.device = device
        self.base_unique_id = config_entry.unique_id
        self.device_name = config_entry.title
        self.model = MerossModel(config_entry.data[CONF_MODEL])
        self._ready_event = asyncio.Event()
        self._was_unavailable = True
        self._stale_unsub: CALLBACK_TYPE | None = None
        self._adv_waiters: list[asyncio.Event] = []

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
        except TimeoutError:
            return False
        else:
            return True
        finally:
            self._adv_waiters.remove(event)

    @callback
    def _async_cancel_stale_timer(self) -> None:
        if self._stale_unsub is not None:
            self._stale_unsub()
            self._stale_unsub = None

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
        LOGGER.info(
            "%s: no parseable BLE advertisement for %ss; marking unavailable",
            self.address,
            ADVERTISEMENT_STALE_SECONDS,
        )
        self.async_update_listeners()

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        return (
            self.hass.state is CoreState.running
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
    @override
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        # HA's async_track_unavailable (~30s) fires on missed scans even when
        # firmware is still advertising. Ignore it; offline is decided only by
        # the stale timer after parseable advertisements stop.
        self._last_name = service_info.name

    @callback
    @override
    def _async_stop(self) -> None:
        self._async_cancel_stale_timer()
        super()._async_stop()

    @callback
    @override
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        self.ble_device = service_info.device
        self.device.update_ble_device(service_info.device)
        recovered = self._was_unavailable or not self.available
        raw_hex = _meross_service_data_hex(service_info) or "(none)"

        adv = parse_advertisement_data(
            service_info.device, service_info.advertisement, self.model
        )
        if not adv or "status" not in adv.data:
            LOGGER.debug(
                "%s: advertisement could not be parsed (service_data=%s)",
                service_info.address,
                raw_hex,
            )
            return
        self.device.update_from_advertisement(adv)
        self._ready_event.set()
        self._async_schedule_stale_timer()
        self._async_notify_advertisement_waiters()
        if recovered:
            self._was_unavailable = False
            LOGGER.info("%s: Meross BLE device is available", self.address)
        super()._async_handle_bluetooth_event(service_info, change)

    async def async_wait_ready(self) -> bool:
        """Wait until the first parseable advertisement is received."""
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(DEVICE_STARTUP_TIMEOUT):
                await self._ready_event.wait()
            return True
        return False
