"""Coordinator for the ToGrill Bluetooth integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging

from bleak.exc import BleakError
from togrill_bluetooth.client import Client
from togrill_bluetooth.exceptions import DecodeError
from togrill_bluetooth.packets import (
    Packet,
    PacketA0Notify,
    PacketA1Notify,
    PacketA8Write,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PROBE_COUNT, DOMAIN

type ToGrillConfigEntry = ConfigEntry[ToGrillCoordinator]

SCAN_INTERVAL = timedelta(seconds=30)
LOGGER = logging.getLogger(__name__)


def get_version_string(packet: PacketA0Notify) -> str:
    """Construct a version string from packet data."""
    return f"{packet.version_major}.{packet.version_minor}"


class DeviceNotFound(UpdateFailed):
    """Update failed due to device disconnected."""


class DeviceFailed(UpdateFailed):
    """Update failed due to device disconnected."""


class ToGrillCoordinator(DataUpdateCoordinator[dict[tuple[int, int | None], Packet]]):
    """Class to manage fetching data."""

    config_entry: ToGrillConfigEntry
    client: Client | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ToGrillConfigEntry,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
            name="ToGrill",
            update_interval=SCAN_INTERVAL,
        )
        self.address: str = config_entry.data[CONF_ADDRESS]
        self.data = {}
        self._packet_listeners: list[Callable[[Packet], None]] = []

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            connections={(CONNECTION_BLUETOOTH, self.address)},
            identifiers={(DOMAIN, self.address)},
            name=config_entry.data[CONF_MODEL],
            model_id=config_entry.data[CONF_MODEL],
        )

        config_entry.async_on_unload(
            async_register_callback(
                hass,
                self._async_handle_bluetooth_event,
                BluetoothCallbackMatcher(address=self.address, connectable=True),
                BluetoothScanningMode.ACTIVE,
            )
        )

    def get_device_info(self, probe_number: int | None) -> DeviceInfo:
        """Return device info."""

        if probe_number is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self.address)},
            )

        return DeviceInfo(
            translation_key="probe",
            translation_placeholders={
                "probe_number": str(probe_number),
            },
            identifiers={(DOMAIN, f"{self.address}_{probe_number}")},
            via_device=(DOMAIN, self.address),
        )

    @callback
    def async_add_packet_listener(
        self, packet_callback: Callable[[Packet], None]
    ) -> Callable[[], None]:
        """Add a listener for a given packet type."""

        def _unregister():
            self._packet_listeners.remove(packet_callback)

        self._packet_listeners.append(packet_callback)
        return _unregister

    def async_update_packet_listeners(self, packet: Packet):
        """Update all packet listeners."""
        for listener in self._packet_listeners:
            listener(packet)

    async def _connect_and_update_registry(self) -> Client:
        """Update device registry data."""
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if not device:
            raise DeviceNotFound("Unable to find device")

        try:
            client = await Client.connect(
                device,
                self._notify_callback,
                disconnected_callback=self._disconnected_callback,
            )
        except BleakError as exc:
            self.logger.debug("Connection failed", exc_info=True)
            raise DeviceNotFound("Unable to connect to device") from exc

        try:
            packet_a0 = await client.read(PacketA0Notify)
        except (BleakError, DecodeError) as exc:
            await client.disconnect()
            raise DeviceFailed(f"Device failed {exc}") from exc

        config_entry = self.config_entry

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, self.address)},
            sw_version=get_version_string(packet_a0),
        )

        return client

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect from device."""
        await super().async_shutdown()
        if self.client:
            await self.client.disconnect()
        self.client = None

    async def _get_connected_client(self) -> Client:
        if self.client:
            return self.client

        self.client = await self._connect_and_update_registry()
        return self.client

    def get_packet[PacketT: Packet](
        self, packet_type: type[PacketT], probe=None
    ) -> PacketT | None:
        """Get a cached packet of a certain type."""

        if packet := self.data.get((packet_type.type, probe)):
            assert isinstance(packet, packet_type)
            return packet
        return None

    def _notify_callback(self, packet: Packet):
        probe = getattr(packet, "probe", None)
        self.data[(packet.type, probe)] = packet
        self.async_update_packet_listeners(packet)
        self.async_update_listeners()

    async def _async_update_data(self) -> dict[tuple[int, int | None], Packet]:
        """Poll the device."""
        if self.client and not self.client.is_connected:
            await self.client.disconnect()
            self.client = None
            self._async_request_refresh_soon()
            raise DeviceFailed("Device was disconnected")

        client = await self._get_connected_client()
        try:
            await client.request(PacketA0Notify)
            await client.request(PacketA1Notify)
            for probe in range(1, self.config_entry.data[CONF_PROBE_COUNT] + 1):
                await client.write(PacketA8Write(probe=probe))
        except BleakError as exc:
            raise DeviceFailed(f"Device failed {exc}") from exc
        return self.data

    @callback
    def _async_request_refresh_soon(self) -> None:
        self.config_entry.async_create_task(
            self.hass, self.async_request_refresh(), eager_start=False
        )

    @callback
    def _disconnected_callback(self) -> None:
        """Handle Bluetooth device being disconnected."""
        self._async_request_refresh_soon()

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        if isinstance(self.last_exception, DeviceNotFound):
            self._async_request_refresh_soon()
