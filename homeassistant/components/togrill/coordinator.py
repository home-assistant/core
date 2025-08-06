"""Coordinator for the ToGrill Bluetooth integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from bleak.exc import BleakError
from togrill_bluetooth.client import Client
from togrill_bluetooth.packets import Packet, PacketA0Notify, PacketA1Notify

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

type ToGrillConfigEntry = ConfigEntry[ToGrillCoordinator]

SCAN_INTERVAL = timedelta(seconds=30)
LOGGER = logging.getLogger(__name__)


class DeviceNotFound(UpdateFailed):
    """Update failed due to device disconnected."""


class DeviceFailed(UpdateFailed):
    """Update failed due to device disconnected."""


class ToGrillCoordinator(DataUpdateCoordinator[dict[int, Packet]]):
    """Class to manage fetching data."""

    config_entry: ToGrillConfigEntry
    client: Client | None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ToGrillConfigEntry,
        logger: logging.Logger,
        address: str,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            config_entry=config_entry,
            name="ToGrill",
            update_interval=SCAN_INTERVAL,
        )
        self.address = address
        self.data = {}
        self.device_info = DeviceInfo(
            name=config_entry.title, connections={(CONNECTION_BLUETOOTH, address)}
        )

        self.client = None

        config_entry.async_on_unload(
            async_register_callback(
                hass,
                self._async_handle_bluetooth_event,
                BluetoothCallbackMatcher(address=self.address, connectable=True),
                BluetoothScanningMode.ACTIVE,
            )
        )

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect from device."""
        await super().async_shutdown()
        if self.client:
            await self.client.disconnect()
        self.client = None

    async def _get_connected_client(self) -> Client:
        if self.client and not self.client.is_connected:
            await self.client.disconnect()
            self.client = None
        if self.client:
            return self.client

        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if not device:
            raise DeviceNotFound("Unable to find device")

        self.client = await Client.connect(device, self._notify_callback)
        return self.client

    def _notify_callback(self, packet: Packet):
        self.data[packet.type] = packet
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[int, Packet]:
        """Poll the device."""
        try:
            client = await self._get_connected_client()
            await client.request(PacketA0Notify)
            await client.request(PacketA1Notify)
        except BleakError as exc:
            raise DeviceFailed(f"Device failed {exc}") from exc
        return self.data

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        if not self.client and isinstance(self.last_exception, DeviceNotFound):
            self.hass.async_create_task(self.async_refresh())
