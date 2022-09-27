"""Bluetooth scanner for esphome."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import datetime
from datetime import timedelta
import re
import time
from typing import Any
import uuid

from aioesphomeapi import APIClient, BluetoothLEAdvertisement
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.client import BaseBleakClient, NotifyCallback
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    BaseHaScanner,
    HaBluetoothConnector,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    async_get_hass,
    callback as hass_callback,
)
from homeassistant.helpers.event import async_track_time_interval

from ..domain_data import DomainData
from ..entry_data import RuntimeEntryData
from .characteristic import BleakGATTCharacteristicESPHome
from .descriptor import BleakGATTDescriptorESPHome
from .service import BleakGATTServiceESPHome

ADV_STALE_TIME = 180  # seconds

TWO_CHAR = re.compile("..")
DEFAULT_MTU = 23
GATT_HEADER_SIZE = 3
DEFAULT_MAX_WRITE_WITHOUT_RESPONSE = DEFAULT_MTU - GATT_HEADER_SIZE


def mac_to_int(address: str) -> int:
    """Convert a mac address to an integer."""
    return int(address.replace(":", ""), 16)


@hass_callback
def async_can_connect(source: str) -> bool:
    """Check if a given source can make another connection."""
    domain_data = DomainData.get(async_get_hass())
    client = domain_data.get_entry_data(domain_data.get_by_unique_id(source)).client
    return True


#    return bool(client.available_ble_connections)


async def async_connect_scanner(
    hass: HomeAssistant,
    entry: ConfigEntry,
    cli: APIClient,
    entry_data: RuntimeEntryData,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    assert entry.unique_id is not None
    source = str(entry.unique_id)
    new_info_callback = async_get_advertisement_callback(hass)
    connectable = True  # TODO: check for 2022.10+
    connector = HaBluetoothConnector(
        client=ESPHomeClient,
        source=source,
        can_connect=lambda: async_can_connect(source),
    )
    scanner = ESPHomeScanner(hass, source, new_info_callback, connector, connectable)
    unload_callbacks = [
        async_register_scanner(hass, scanner, False),
        scanner.async_setup(),
    ]
    await cli.subscribe_bluetooth_le_advertisements(scanner.async_on_advertisement)
    entry_data.bluetooth_scanner = scanner

    @hass_callback
    def _async_unload() -> None:
        entry_data.bluetooth_scanner = None
        for callback in unload_callbacks:
            callback()

    return _async_unload


class ESPHomeScanner(BaseHaScanner):
    """Scanner for esphome."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        self._hass = hass
        self._new_info_callback = new_info_callback
        self._discovered_devices: dict[str, BLEDevice] = {}
        self._discovered_device_timestamps: dict[str, float] = {}
        self._source = scanner_id
        self._connector = connector
        self._connectable = connectable

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        return async_track_time_interval(
            self._hass, self._async_expire_devices, timedelta(seconds=30)
        )

    def _async_expire_devices(self, _datetime: datetime.datetime) -> None:
        """Expire old devices."""
        now = time.monotonic()
        expired = [
            address
            for address, timestamp in self._discovered_device_timestamps.items()
            if now - timestamp > ADV_STALE_TIME
        ]
        for address in expired:
            del self._discovered_devices[address]
            del self._discovered_device_timestamps[address]

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return a list of discovered devices."""
        return list(self._discovered_devices.values())

    async def async_get_device_by_address(self, address: str) -> BLEDevice | None:
        """Get a device by address."""
        return self._discovered_devices.get(address)

    @hass_callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        now = time.monotonic()
        address = ":".join(TWO_CHAR.findall("%012X" % adv.address))  # must be upper
        advertisement_data = AdvertisementData(  # type: ignore[no-untyped-call]
            local_name=None if adv.name == "" else adv.name,
            manufacturer_data=adv.manufacturer_data,
            service_data=adv.service_data,
            service_uuids=adv.service_uuids,
        )
        details = {"connector": self._connector} if self._connectable else {}
        device = BLEDevice(  # type: ignore[no-untyped-call]
            address=address,
            name=adv.name,
            details=details,
            rssi=adv.rssi,
        )
        self._discovered_devices[address] = device
        self._discovered_device_timestamps[address] = now
        self._new_info_callback(
            BluetoothServiceInfoBleak(
                name=advertisement_data.local_name or device.name or device.address,
                address=device.address,
                rssi=device.rssi,
                manufacturer_data=advertisement_data.manufacturer_data,
                service_data=advertisement_data.service_data,
                service_uuids=advertisement_data.service_uuids,
                source=self._source,
                device=device,
                advertisement=advertisement_data,
                connectable=False,
                time=now,
            )
        )


class ESPHomeClient(BaseBleakClient):
    """ESPHome Bleak Client."""

    def __init__(
        self, address_or_ble_device: BLEDevice | str, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize the ESPHomeClient."""
        assert isinstance(address_or_ble_device, BLEDevice)
        super().__init__(address_or_ble_device, *args, **kwargs)
        self._ble_device = address_or_ble_device
        self._address_as_int = mac_to_int(self._ble_device.address)
        assert self._ble_device.details is not None
        self._source = self._ble_device.details["source"]
        domain_data = DomainData.get(async_get_hass())
        self._client = domain_data.get_entry_data(
            domain_data.get_by_unique_id(self._source)
        ).client
        self._is_connected = False

    def __str__(self) -> str:
        """Return the string representation of the client."""
        return f"ESPHomeClient ({self.address})"

    def _on_bluetooth_connection_state(self, connected: bool) -> None:
        """Handle a connect or disconnect."""
        self._is_connected = connected
        if connected:
            return
        self.services = BleakGATTServiceCollection()  # type: ignore[no-untyped-call]
        if self._disconnected_callback:
            self._disconnected_callback(self)

    async def connect(self, **kwargs: Any) -> bool:
        """Connect to a specified Peripheral.

        Keyword Args:
            timeout (float): Timeout for required ``BleakScanner.find_device_by_address`` call. Defaults to 10.0.
        Returns:
            Boolean representing connection status.
        """
        timeout = kwargs.get("timeout", self._timeout)
        try:
            await self._client.bluetooth_device_connect(
                self._address_as_int,
                self._on_bluetooth_connection_state,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return False

        # TODO: cache services
        await self.get_services()
        return True

    async def disconnect(self) -> bool:
        """Disconnect from the peripheral device."""
        await self._client.bluetooth_device_disconnect(self._address_as_int)
        return True

    @property
    def is_connected(self) -> bool:
        """Is Connected."""
        return self._is_connected

    @property
    def mtu_size(self) -> int:
        """Get ATT MTU size for active connection."""
        return DEFAULT_MTU

    async def pair(self, *args: Any, **kwargs: Any) -> bool:
        """Attempt to pair."""
        raise NotImplementedError("Pairing is not available in ESPHome.")

    async def unpair(self) -> bool:
        """Attempt to unpair."""
        raise NotImplementedError("Pairing is not available in ESPHome.")

    async def get_services(self, **kwargs: Any) -> BleakGATTServiceCollection:
        """Get all services registered for this GATT server.

        Returns:
           A :py:class:`bleak.backends.service.BleakGATTServiceCollection` with this device's services tree.
        """
        esphome_services = await self._client.bluetooth_gatt_get_services(
            self._address_as_int
        )
        services = BleakGATTServiceCollection()  # type: ignore[no-untyped-call]
        for service in esphome_services.services:
            services.add_service(BleakGATTServiceESPHome(service))
            for characteristic in service.characteristics:
                services.add_characteristic(
                    BleakGATTCharacteristicESPHome(
                        characteristic,
                        DEFAULT_MAX_WRITE_WITHOUT_RESPONSE,
                        service.uuid,
                        service.handle,
                    )
                )
                for descriptor in characteristic.descriptors:
                    self.services.add_descriptor(
                        BleakGATTDescriptorESPHome(
                            descriptor,
                            characteristic.uuid,
                            characteristic.handle,
                        )
                    )
        self.services = services
        return services

    def _resolve_characteristic(
        self, char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID
    ) -> BleakGATTCharacteristic:
        """Resolve a characteristic specifier to a BleakGATTCharacteristic object."""
        if not isinstance(char_specifier, BleakGATTCharacteristic):
            characteristic = self.services.get_characteristic(char_specifier)
        else:
            characteristic = char_specifier
        if not characteristic:
            raise BleakError(f"Characteristic {char_specifier} was not found!")
        return characteristic

    async def read_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
        use_cached: bool = False,
        **kwargs: Any,
    ) -> bytearray:
        """Perform read operation on the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to read from,
                specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristic object representing it.
            use_cached (bool): `False` forces macOS to read the value from the
                device again and not use its own cached value. Defaults to `False`.
        Returns:
            (bytearray) The read data.
        """
        characteristic = self._resolve_characteristic(char_specifier)
        return await self._client.bluetooth_gatt_read(
            self._address_as_int, characteristic.service_uuid, characteristic.uuid
        )

    async def read_gatt_descriptor(
        self, handle: int, use_cached: bool = False, **kwargs: Any
    ) -> bytearray:
        """Perform read operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            use_cached (bool): `False` forces Windows to read the value from the
                device again and not use its own cached value. Defaults to `False`.
        Returns:
            (bytearray) The read data.
        """
        raise NotImplementedError

    async def write_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
        data: bytes | bytearray | memoryview,
        response: bool = False,
    ) -> None:
        """Perform a write operation of the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to write
                to, specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristic object representing it.
            data (bytes or bytearray): The data to send.
            response (bool): If write-with-response operation should be done. Defaults to `False`.
        """
        characteristic = self._resolve_characteristic(char_specifier)
        await self._client.bluetooth_gatt_write(
            self._address_as_int, characteristic.service_uuid, characteristic.uuid, data
        )

    async def write_gatt_descriptor(
        self, handle: int, data: bytes | bytearray | memoryview
    ) -> None:
        """Perform a write operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            data (bytes or bytearray): The data to send.
        """
        raise NotImplementedError

    async def start_notify(
        self,
        characteristic: BleakGATTCharacteristic,
        callback: NotifyCallback,
        **kwargs: Any,
    ) -> None:
        """Activate notifications/indications on a characteristic.

        Callbacks must accept two inputs. The first will be a integer handle of the characteristic generating the
        data and the second will be a ``bytearray`` containing the data sent from the connected server.
        .. code-block:: python
            def callback(sender: int, data: bytearray):
                print(f"{sender}: {data}")
            client.start_notify(char_uuid, callback)
        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to activate
                notifications/indications on a characteristic, specified by either integer handle,
                UUID or directly by the BleakGATTCharacteristic object representing it.
            callback (function): The function to be called on notification.
        """
        raise NotImplementedError

    async def stop_notify(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
    ) -> None:
        """Deactivate notification/indication on a specified characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to deactivate
                notification/indication on, specified by either integer handle, UUID or
                directly by the BleakGATTCharacteristic object representing it.
        """
        characteristic = self._resolve_characteristic(char_specifier)
        raise NotImplementedError
