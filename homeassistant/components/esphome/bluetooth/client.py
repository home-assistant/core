"""Bluetooth client for esphome."""
from __future__ import annotations

import asyncio
from typing import Any
import uuid

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.client import BaseBleakClient, NotifyCallback
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakError

from homeassistant.core import async_get_hass

from ..domain_data import DomainData
from .characteristic import BleakGATTCharacteristicESPHome
from .descriptor import BleakGATTDescriptorESPHome
from .service import BleakGATTServiceESPHome

DEFAULT_MTU = 23
GATT_HEADER_SIZE = 3
DEFAULT_MAX_WRITE_WITHOUT_RESPONSE = DEFAULT_MTU - GATT_HEADER_SIZE


def mac_to_int(address: str) -> int:
    """Convert a mac address to an integer."""
    return int(address.replace(":", ""), 16)


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
        self.domain_data = DomainData.get(async_get_hass())
        self._client = self.domain_data.get_entry_data(
            self.domain_data.get_by_unique_id(self._source)
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

    async def connect(
        self, dangerous_use_bleak_cache: bool = False, **kwargs: Any
    ) -> bool:
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

        await self.get_services(dangerous_use_bleak_cache=dangerous_use_bleak_cache)
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

    async def get_services(
        self, dangerous_use_bleak_cache: bool = False, **kwargs: Any
    ) -> BleakGATTServiceCollection:
        """Get all services registered for this GATT server.

        Returns:
           A :py:class:`bleak.backends.service.BleakGATTServiceCollection` with this device's services tree.
        """
        address_as_int = self._address_as_int
        domain_data = self.domain_data
        if dangerous_use_bleak_cache and (
            cached_services := domain_data.get_gatt_services_cache(address_as_int)
        ):
            self.services = cached_services
            return self.services
        esphome_services = await self._client.bluetooth_gatt_get_services(
            address_as_int
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
        if dangerous_use_bleak_cache:
            domain_data.set_gatt_services_cache(address_as_int, services)
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
        return await self._client.bluetooth_gatt_read_descriptor(
            self._address_as_int, handle
        )

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
        await self._client.bluetooth_gatt_write_descriptor(
            self._address_as_int, handle, data
        )

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
        await self._client.bluetooth_gatt_start_notify(
            self._address_as_int,
            characteristic.service_uuid,
            characteristic.uuid,
            callback,
        )

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
        await self._client.bluetooth_gatt_stop_notify(
            self._address_as_int, characteristic.service_uuid, characteristic.uuid
        )
