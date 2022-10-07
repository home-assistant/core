"""Bluetooth client for esphome."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any, TypeVar, cast
import uuid

from aioesphomeapi.connection import APIConnectionError, TimeoutAPIError
import async_timeout
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.client import BaseBleakClient, NotifyCallback
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
from bleak.exc import BleakError

from homeassistant.core import CALLBACK_TYPE, async_get_hass

from ..domain_data import DomainData
from .characteristic import BleakGATTCharacteristicESPHome
from .descriptor import BleakGATTDescriptorESPHome
from .service import BleakGATTServiceESPHome

DEFAULT_MTU = 23
GATT_HEADER_SIZE = 3
DISCONNECT_TIMEOUT = 5.0
CONNECT_FREE_SLOT_TIMEOUT = 2.0
GATT_READ_TIMEOUT = 30.0

DEFAULT_MAX_WRITE_WITHOUT_RESPONSE = DEFAULT_MTU - GATT_HEADER_SIZE
_LOGGER = logging.getLogger(__name__)

_WrapFuncType = TypeVar(  # pylint: disable=invalid-name
    "_WrapFuncType", bound=Callable[..., Any]
)


def mac_to_int(address: str) -> int:
    """Convert a mac address to an integer."""
    return int(address.replace(":", ""), 16)


def verify_connected(func: _WrapFuncType) -> _WrapFuncType:
    """Define a wrapper throw BleakError if not connected."""

    async def _async_wrap_bluetooth_connected_operation(
        self: "ESPHomeClient", *args: Any, **kwargs: Any
    ) -> Any:
        if not self._is_connected:  # pylint: disable=protected-access
            raise BleakError("Not connected")
        return await func(self, *args, **kwargs)

    return cast(_WrapFuncType, _async_wrap_bluetooth_connected_operation)


def api_error_as_bleak_error(func: _WrapFuncType) -> _WrapFuncType:
    """Define a wrapper throw esphome api errors as BleakErrors."""

    async def _async_wrap_bluetooth_operation(
        self: "ESPHomeClient", *args: Any, **kwargs: Any
    ) -> Any:
        try:
            return await func(self, *args, **kwargs)
        except TimeoutAPIError as err:
            raise asyncio.TimeoutError(str(err)) from err
        except APIConnectionError as err:
            raise BleakError(str(err)) from err

    return cast(_WrapFuncType, _async_wrap_bluetooth_operation)


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
        config_entry = self.domain_data.get_by_unique_id(self._source)
        self.entry_data = self.domain_data.get_entry_data(config_entry)
        self._client = self.entry_data.client
        self._is_connected = False
        self._mtu: int | None = None
        self._cancel_connection_state: CALLBACK_TYPE | None = None
        self._notify_cancels: dict[int, Callable[[], Coroutine[Any, Any, None]]] = {}

    def __str__(self) -> str:
        """Return the string representation of the client."""
        return f"ESPHomeClient ({self.address})"

    def _unsubscribe_connection_state(self) -> None:
        """Unsubscribe from connection state updates."""
        if not self._cancel_connection_state:
            return
        try:
            self._cancel_connection_state()
        except (AssertionError, ValueError) as ex:
            _LOGGER.debug(
                "Failed to unsubscribe from connection state (likely connection dropped): %s",
                ex,
            )
        self._cancel_connection_state = None

    def _async_ble_device_disconnected(self) -> None:
        """Handle the BLE device disconnecting from the ESP."""
        _LOGGER.debug("%s: BLE device disconnected", self._source)
        self._is_connected = False
        self.services = BleakGATTServiceCollection()  # type: ignore[no-untyped-call]
        self._async_call_bleak_disconnected_callback()
        self._unsubscribe_connection_state()

    def _async_esp_disconnected(self) -> None:
        """Handle the esp32 client disconnecting from hass."""
        _LOGGER.debug("%s: ESP device disconnected", self._source)
        self.entry_data.disconnect_callbacks.remove(self._async_esp_disconnected)
        self._async_ble_device_disconnected()

    def _async_call_bleak_disconnected_callback(self) -> None:
        """Call the disconnected callback to inform the bleak consumer."""
        if self._disconnected_callback:
            self._disconnected_callback(self)
            self._disconnected_callback = None

    @api_error_as_bleak_error
    async def connect(
        self, dangerous_use_bleak_cache: bool = False, **kwargs: Any
    ) -> bool:
        """Connect to a specified Peripheral.

        Keyword Args:
            timeout (float): Timeout for required ``BleakScanner.find_device_by_address`` call. Defaults to 10.0.
        Returns:
            Boolean representing connection status.
        """
        await self._wait_for_free_connection_slot(CONNECT_FREE_SLOT_TIMEOUT)

        connected_future: asyncio.Future[bool] = asyncio.Future()

        def _on_bluetooth_connection_state(
            connected: bool, mtu: int, error: int
        ) -> None:
            """Handle a connect or disconnect."""
            _LOGGER.debug(
                "Connection state changed: connected=%s mtu=%s error=%s",
                connected,
                mtu,
                error,
            )
            if connected:
                self._is_connected = True
                self._mtu = mtu
            else:
                self._async_ble_device_disconnected()

            if connected_future.done():
                return

            if error:
                connected_future.set_exception(
                    BleakError(f"Error while connecting: {error}")
                )
                return

            if not connected:
                connected_future.set_exception(BleakError("Disconnected"))
                return

            self.entry_data.disconnect_callbacks.append(self._async_esp_disconnected)
            connected_future.set_result(connected)

        timeout = kwargs.get("timeout", self._timeout)
        self._cancel_connection_state = await self._client.bluetooth_device_connect(
            self._address_as_int,
            _on_bluetooth_connection_state,
            timeout=timeout,
        )
        await connected_future
        await self.get_services(dangerous_use_bleak_cache=dangerous_use_bleak_cache)
        return True

    @api_error_as_bleak_error
    async def disconnect(self) -> bool:
        """Disconnect from the peripheral device."""
        self._unsubscribe_connection_state()
        await self._client.bluetooth_device_disconnect(self._address_as_int)
        await self._wait_for_free_connection_slot(DISCONNECT_TIMEOUT)
        return True

    async def _wait_for_free_connection_slot(self, timeout: float) -> None:
        """Wait for a free connection slot."""
        if self.entry_data.ble_connections_free:
            return
        _LOGGER.debug(
            "%s: Out of connection slots, waiting for a free one", self._source
        )
        async with async_timeout.timeout(timeout):
            await self.entry_data.wait_for_ble_connections_free()

    @property
    def is_connected(self) -> bool:
        """Is Connected."""
        return self._is_connected

    @property
    def mtu_size(self) -> int:
        """Get ATT MTU size for active connection."""
        return self._mtu or DEFAULT_MTU

    @verify_connected
    @api_error_as_bleak_error
    async def pair(self, *args: Any, **kwargs: Any) -> bool:
        """Attempt to pair."""
        raise NotImplementedError("Pairing is not available in ESPHome.")

    @verify_connected
    @api_error_as_bleak_error
    async def unpair(self) -> bool:
        """Attempt to unpair."""
        raise NotImplementedError("Pairing is not available in ESPHome.")

    @api_error_as_bleak_error
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
            _LOGGER.debug(
                "Cached services hit for %s - %s",
                self._ble_device.name,
                self._ble_device.address,
            )
            self.services = cached_services
            return self.services
        _LOGGER.debug(
            "Cached services miss for %s - %s",
            self._ble_device.name,
            self._ble_device.address,
        )
        esphome_services = await self._client.bluetooth_gatt_get_services(
            address_as_int
        )
        max_write_without_response = self.mtu_size - GATT_HEADER_SIZE
        services = BleakGATTServiceCollection()  # type: ignore[no-untyped-call]
        for service in esphome_services.services:
            services.add_service(BleakGATTServiceESPHome(service))
            for characteristic in service.characteristics:
                services.add_characteristic(
                    BleakGATTCharacteristicESPHome(
                        characteristic,
                        max_write_without_response,
                        service.uuid,
                        service.handle,
                    )
                )
                for descriptor in characteristic.descriptors:
                    services.add_descriptor(
                        BleakGATTDescriptorESPHome(
                            descriptor,
                            characteristic.uuid,
                            characteristic.handle,
                        )
                    )
        self.services = services
        _LOGGER.debug(
            "Cached services saved for %s - %s",
            self._ble_device.name,
            self._ble_device.address,
        )
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

    @verify_connected
    @api_error_as_bleak_error
    async def read_gatt_char(
        self,
        char_specifier: BleakGATTCharacteristic | int | str | uuid.UUID,
        **kwargs: Any,
    ) -> bytearray:
        """Perform read operation on the specified GATT characteristic.

        Args:
            char_specifier (BleakGATTCharacteristic, int, str or UUID): The characteristic to read from,
                specified by either integer handle, UUID or directly by the
                BleakGATTCharacteristic object representing it.
        Returns:
            (bytearray) The read data.
        """
        characteristic = self._resolve_characteristic(char_specifier)
        return await self._client.bluetooth_gatt_read(
            self._address_as_int, characteristic.handle, GATT_READ_TIMEOUT
        )

    @verify_connected
    @api_error_as_bleak_error
    async def read_gatt_descriptor(self, handle: int, **kwargs: Any) -> bytearray:
        """Perform read operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
        Returns:
            (bytearray) The read data.
        """
        return await self._client.bluetooth_gatt_read_descriptor(
            self._address_as_int, handle, GATT_READ_TIMEOUT
        )

    @verify_connected
    @api_error_as_bleak_error
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
            self._address_as_int, characteristic.handle, bytes(data), response
        )

    @verify_connected
    @api_error_as_bleak_error
    async def write_gatt_descriptor(
        self, handle: int, data: bytes | bytearray | memoryview
    ) -> None:
        """Perform a write operation on the specified GATT descriptor.

        Args:
            handle (int): The handle of the descriptor to read from.
            data (bytes or bytearray): The data to send.
        """
        await self._client.bluetooth_gatt_write_descriptor(
            self._address_as_int, handle, bytes(data)
        )

    @verify_connected
    @api_error_as_bleak_error
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
        cancel_coro = await self._client.bluetooth_gatt_start_notify(
            self._address_as_int,
            characteristic.handle,
            lambda handle, data: callback(data),
        )
        self._notify_cancels[characteristic.handle] = cancel_coro

    @api_error_as_bleak_error
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
        coro = self._notify_cancels.pop(characteristic.handle)
        await coro()
