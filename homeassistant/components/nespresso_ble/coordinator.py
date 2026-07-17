"""Coordinator for the Nespresso integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from bleak import BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import close_stale_connections_by_address
from nespresso_ble import NespressoBluetoothDeviceData, NespressoDevice, NespressoError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type NespressoBLEConfigEntry = ConfigEntry[NespressoBLECoordinator]


class NespressoBLECoordinator(DataUpdateCoordinator[NespressoDevice]):
    """Coordinator to fetch data from a Nespresso machine over BLE."""

    config_entry: NespressoBLEConfigEntry

    def __init__(self, hass: HomeAssistant, entry: NespressoBLEConfigEntry) -> None:
        """Initialize the coordinator."""
        self._client = NespressoBluetoothDeviceData(_LOGGER)
        self._stream_task: asyncio.Task[None] | None = None
        self._stop_stream: asyncio.Event | None = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @override
    async def _async_setup(self) -> None:
        """Clean up stale connections before the first refresh."""
        address = self.config_entry.unique_id
        assert address is not None
        await close_stale_connections_by_address(address)

    def _async_get_ble_device(self) -> BLEDevice:
        """Return a fresh BLE device for the configured address."""
        address = self.config_entry.unique_id
        assert address is not None
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, address, connectable=True
        )
        if ble_device is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={
                    "address": address,
                    "reason": bluetooth.async_address_reachability_diagnostics(
                        self.hass,
                        address.upper(),
                        BluetoothReachabilityIntent.CONNECTION,
                    ),
                },
            )
        return ble_device

    @override
    async def _async_update_data(self) -> NespressoDevice:
        """Fetch the latest data and (re)start push streaming if supported."""
        ble_device = self._async_get_ble_device()
        try:
            device = await self._client.update_device(ble_device)
        except (BleakError, NespressoError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        service_info = bluetooth.async_last_service_info(
            self.hass, ble_device.address, connectable=True
        )
        service_uuids = service_info.service_uuids if service_info else []
        if self._client.supports_push(service_uuids) and (
            self._stream_task is None or self._stream_task.done()
        ):
            self._start_stream(ble_device)
        return device

    def _start_stream(self, ble_device: BLEDevice) -> None:
        """Start a background task streaming push updates from the machine."""
        self._stop_stream = asyncio.Event()

        @callback
        def _on_update(device: NespressoDevice) -> None:
            self.async_set_updated_data(device)

        async def _run() -> None:
            try:
                await self._client.stream(ble_device, _on_update, self._stop_stream)
            except (BleakError, NespressoError) as err:
                _LOGGER.debug("Push stream ended for %s: %s", ble_device.address, err)

        self._stream_task = self.config_entry.async_create_background_task(
            self.hass, _run(), f"{DOMAIN}_stream_{ble_device.address}"
        )

    @override
    async def async_shutdown(self) -> None:
        """Stop the push stream and shut the coordinator down."""
        if self._stop_stream is not None:
            self._stop_stream.set()
        if self._stream_task is not None:
            self._stream_task.cancel()
        await super().async_shutdown()
