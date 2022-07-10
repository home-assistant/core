"""The BLE Parser integration."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
import logging
from typing import Any

from bleparser import BleParser

from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.components.bluetooth.device import BluetoothDeviceData
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .sensor import MAPPINGS as SENSOR_MAPPINGS
from .util import address_to_bytes, manufacturer_data_to_raw

_LOGGER = logging.getLogger(__name__)
PARSER = BleParser(
    discovery=True, filter_duplicates=True, sensor_whitelist=[], tracker_whitelist=[]
)


@callback
def async_get_manufacturer_parser(
    device_data: BluetoothDeviceData,
    parser: Callable[[Any, bytes, bytes, int], dict[str, Any]],
) -> BLEManufacturerParserWrapper:
    """Return manufacturer parser wrapper."""
    return BLEManufacturerParserWrapper(device_data, parser)


@callback
def async_get_manufacturer_parser_with_local_name(
    device_data: BluetoothDeviceData,
    parser: Callable[[Any, bytes, str, bytes, int], dict[str, Any]],
) -> BLEManufacturerParserWithLocalNameWrapper:
    """Return manufacturer parser wrapper that needs a local name."""
    return BLEManufacturerParserWithLocalNameWrapper(device_data, parser)


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
                    key=data_type,
                    native_value=value,
                    **sensor_mapping,
                )


class BLEManufacturerParserWrapperBase(BLEParserWrapperBase):
    """BLE Parser Wrapper."""

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
        """Load BLE Parser to Bluetooth Device Data.

        This is for devices that put the whole payload in the manufacturer data.
        We need to extract only the newest data.
        """
        if service_info.manufacturer_data:
            self.async_load_manufacturer_data_id(
                service_info, list(service_info.manufacturer_data)[-1]
            )


class BLEManufacturerParserWrapper(BLEManufacturerParserWrapperBase):
    """BLE Parser Wrapper."""

    def __init__(
        self,
        device_data: BluetoothDeviceData,
        parser: Callable[[Any, bytes, bytes, int], dict[str, Any]],
    ) -> None:
        """Initialize BLE Parser Wrapper."""
        self.parser = parser
        super().__init__(device_data)

    @callback
    def async_load_manufacturer_data_id(
        self, service_info: BluetoothServiceInfo, manufacturer_id: int
    ) -> None:
        """Load BLE Parser to Bluetooth Device Data for a given id."""
        raw = manufacturer_data_to_raw(
            manufacturer_id, service_info.manufacturer_data[manufacturer_id]
        )
        try:
            parsed = self.parser(
                PARSER,
                raw,
                address_to_bytes(service_info.address),
                service_info.rssi,
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Error parsing BLE data: %s (%s): %s", service_info, raw, ex
            )
            return
        _LOGGER.debug("Loading parsed BLE data: %s from %s", parsed, service_info)
        self.async_load(parsed)


class BLEManufacturerParserWithLocalNameWrapper(BLEManufacturerParserWrapperBase):
    """BLE Parser with local name Wrapper."""

    def __init__(
        self,
        device_data: BluetoothDeviceData,
        parser: Callable[[Any, bytes, str, bytes, int], dict[str, Any]],
    ) -> None:
        """Initialize BLE Parser Wrapper."""
        self.parser = parser
        super().__init__(device_data)

    @callback
    def async_load_manufacturer_data_id(
        self, service_info: BluetoothServiceInfo, manufacturer_id: int
    ) -> None:
        """Load BLE Parser to Bluetooth Device Data for a given id."""
        raw = manufacturer_data_to_raw(
            manufacturer_id, service_info.manufacturer_data[manufacturer_id]
        )
        try:
            parsed = self.parser(
                PARSER,
                raw,
                service_info.name,
                address_to_bytes(service_info.address),
                service_info.rssi,
            )
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warning(
                "Error parsing BLE data: %s (%s): %s", service_info, raw, ex
            )
            return
        _LOGGER.debug("Loading parsed BLE data: %s from %s", parsed, service_info)
        self.async_load(parsed)
