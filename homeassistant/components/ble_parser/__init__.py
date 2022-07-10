"""The BLE Parser integration."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from typing import Any

from bleparser import BleParser

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.device import BluetoothDeviceData
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .sensor import MAPPINGS as SENSOR_MAPPINGS

PARSER = BleParser(
    discovery=True, filter_duplicates=True, sensor_whitelist=[], tracker_whitelist=[]
)


@callback
def async_get_parser(
    device_data: BluetoothDeviceData,
    parser: Callable[[Any, bytes, bytes, int], dict[str, Any]],
) -> BLEParserWrapper:
    """Return the adapter name."""
    return BLEParserWrapper(device_data, parser)


@callback
def async_get_parser_with_local_name(
    device_data: BluetoothDeviceData,
    parser: Callable[[Any, bytes, str, bytes, int], dict[str, Any]],
) -> BLEParserWithLocalNameWrapper:
    """Return the adapter name."""
    return BLEParserWithLocalNameWrapper(device_data, parser)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up BLE Parser."""
    return True


class BLEParserWrapperBase:
    """BLE Parser Wrapper."""

    def __init__(
        self,
        device_data: BluetoothDeviceData,
    ) -> None:
        """Initialize BLE Parser Wrapper."""
        self.device_data = device_data

    @callback
    @abstractmethod
    def async_load_manufacturer_data_id(
        self, service_info: BluetoothServiceInfo, manufacturer_id: int
    ) -> None:
        """Load BLE Parser to Bluetooth Device Data for a given id."""

    @callback
    def async_load_manufacturer_data(self, service_info: BluetoothServiceInfo) -> None:
        """Load BLE Parser to Bluetooth Device Data."""
        for mgr_id in service_info.manufacturer_data:
            self.async_load_manufacturer_data_id(service_info, mgr_id)

    @callback
    def async_load_newest_manufacturer_data(
        self, service_info: BluetoothServiceInfo
    ) -> None:
        """Load BLE Parser to Bluetooth Device Data."""
        if service_info.manufacturer_data:
            self.async_load_manufacturer_data_id(
                service_info, list(service_info.manufacturer_data)[-1]
            )

    @callback
    def async_load(self, data: dict[str, Any] | None) -> None:
        """Load BLE Parser to Bluetooth Device Data."""
        if not data or not data.get("data"):
            return

        device_data = self.device_data

        if device_type := data.get("type"):
            device_data.set_device_type(device_type)
        if device_name := data.get("name"):
            device_data.set_device_name(device_name)

        for data_type, value in data.items():
            if sensor_mapping := SENSOR_MAPPINGS.get(data_type):
                device_data.update_sensor(
                    key=_ble_parser_data_type_to_description_key(data_type),
                    native_value=value,
                    **sensor_mapping,
                )


class BLEParserWrapper(BLEParserWrapperBase):
    """BLE Parser Wrapper."""

    def __init__(
        self,
        device_data: BluetoothDeviceData,
        parser: Callable[[Any, bytes, bytes, int], dict[str, Any]],
    ) -> None:
        """Initialize BLE Parser Wrapper."""
        self.parser = parser
        self.device_data = device_data
        super().__init__(device_data)

    @callback
    def async_load_manufacturer_data_id(
        self, service_info: BluetoothServiceInfo, manufacturer_id: int
    ) -> None:
        """Load BLE Parser to Bluetooth Device Data for a given id."""
        self.async_load(
            self.parser(
                PARSER,
                _manufacturer_data_to_raw(
                    manufacturer_id, service_info.manufacturer_data[manufacturer_id]
                ),
                address_to_bytes(service_info.address),
                service_info.rssi,
            )
        )


class BLEParserWithLocalNameWrapper(BLEParserWrapperBase):
    """BLE Parser with local name Wrapper."""

    def __init__(
        self,
        device_data: BluetoothDeviceData,
        parser: Callable[[Any, bytes, str, bytes, int], dict[str, Any]],
    ) -> None:
        """Initialize BLE Parser Wrapper."""
        self.parser = parser
        self.device_data = device_data
        super().__init__(device_data)

    @callback
    def async_load_manufacturer_data_id(
        self, service_info: BluetoothServiceInfo, manufacturer_id: int
    ) -> None:
        """Load BLE Parser to Bluetooth Device Data for a given id."""
        self.async_load(
            self.parser(
                PARSER,
                _manufacturer_data_to_raw(
                    manufacturer_id, service_info.manufacturer_data[manufacturer_id]
                ),
                service_info.name,
                address_to_bytes(service_info.address),
                service_info.rssi,
            )
        )


def address_to_bytes(address: str) -> bytes:
    """Return the address as bytes."""
    return bytes(address.replace(":", ""), "utf-8")


def newest_manufacturer_data(service_info: BluetoothServiceInfo) -> bytes:
    """Return the newest manufacturer data from a service info.

    This is for devices that put the whole payload in the manufacturer data.
    We need to extract only the newest data.
    """
    manufacturer_data = service_info.manufacturer_data
    last_id = list(manufacturer_data)[-1]
    return _manufacturer_data_to_raw(last_id, manufacturer_data[last_id])


def _manufacturer_data_to_raw(manufacturer_id: int, manufacturer_data: bytes) -> bytes:
    """Return the raw data from manufacturer data."""
    return _pad_manufacturer_data(
        int(manufacturer_id).to_bytes(2, byteorder="little") + manufacturer_data
    )


def _pad_manufacturer_data(manufacturer_data: bytes) -> bytes:
    """Pad manufacturer data to the format bleparser needs."""
    return b"\x00" * 2 + manufacturer_data


def _ble_parser_data_type_to_description_key(key: str) -> str:
    """Return bluetooth sensor entity description key."""
    return key.replace(" ", "_").lower()
