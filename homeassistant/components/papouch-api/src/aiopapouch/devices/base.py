"""This file contains base classes that define Papouch devices."""

from abc import ABC, abstractmethod
from typing import Any, Protocol
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient
from ..exceptions import DeviceLogicError, DeviceResponseError

ERROR_STATUS = "0"


def find_tag(root: ET.Element, tag_name: str) -> ET.Element | None:
    """Find element and ignore the namespace."""
    for element in root.iter():
        if element.tag.endswith(tag_name):
            return element
    return None


class HttpMixinHost(Protocol):
    """Defines protocol which tells what methods/variables should have a class that uses that protocol. Used for mixin HTTPMixin."""

    @property
    def name(self) -> str:
        """Get the name of the device. MixinHost."""

    @property
    def location(self) -> str:
        """Get the location of the device. MixinHost."""

    api_client: PapouchHTTPClient


class HTTPMixin(HttpMixinHost):
    """Mixin for ETH devices for sending command and checking its response."""

    async def _send_command(
        self,
        cmd_type: str,
        item_id: str | None = None,
        counter: str | None = None,
        time: str | None = None,
        value: str | None = None,
    ) -> None:
        """Send command via network on SET.XML. Parameters will be used in a query."""

        raw_params = {
            "type": cmd_type,
            "id": item_id,
            "cnt": counter,
            "time": time,
            "val": value,
        }
        params = {key: value for key, value in raw_params.items() if value is not None}

        response = await self.api_client.read_command(
            params, f"{self.name} ({self.location})"
        )

        self._check_response(response, str(params))

    def _check_response(self, response_text: str, request_text: str) -> None:
        """Checks the response of the requests."""

        root = defused_ET.fromstring(response_text)
        result_tag = find_tag(root, "result")

        if result_tag is not None:
            status = result_tag.attrib.get("status")

            if status == ERROR_STATUS:
                raise DeviceResponseError(
                    f"{self.name} ({self.location}) - {self.api_client.ip_address} returned an error, "
                    f"whole response: {response_text} and whole request text: {request_text}, "
                    f"whole request text: {request_text}"
                )
        else:
            raise DeviceResponseError(
                f"Response doesn't have the result tag! In the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )


class PapouchDevice(ABC):
    """Abstract class for Papouch devices.

    Beware of the XML namespaces! Some devices can have some while other don't.
    """

    COUNTER_MODES = [
        "off",
        "counts_descending_edges",
        "counts_ascending_edges",
        "counts_ascending_and_descending_edges",
    ]

    SENSOR_TYPES = [
        "unused",
        "temperature_humidity_th15",
        "temperature_ds",
        "temperature_humidity_th3x",
        "temperature_tmp",
    ]

    TEMPERATURE_SNS_TYPE = "1"
    HUMIDITY_SNS_TYPE = "2"
    DEW_POINT_SNS_TYPE = "3"
    CO2_SNS_TYPE = "4"
    PRESSURE_SNS_TYPE = "5"
    WIND_DIRECTION_SNS_TYPE = "6"
    WIND_SPEED_SNS_TYPE = "7"
    RAIN_SNS_TYPE = "8"

    UNIT_MAP = {
        TEMPERATURE_SNS_TYPE: {"0": "°C", "1": "°F", "2": "K"},
        HUMIDITY_SNS_TYPE: {"0": "%"},
        DEW_POINT_SNS_TYPE: {
            "0": "°C",
            "1": "°F",
            "2": "K",
        },
        CO2_SNS_TYPE: {"0": "ppm"},
        PRESSURE_SNS_TYPE: {"0": "hPa"},
        WIND_DIRECTION_SNS_TYPE: {
            "0": "°",
            "1": "",  # METEO returns integer value that maps to a string (e.g. 2 is NNE)
        },
        WIND_SPEED_SNS_TYPE: {"0": "m/s", "1": "km/h"},
        RAIN_SNS_TYPE: {"0": "mm/15 min", "1": "mm/h", "2": "mm/d"},
    }

    def _get_unit(self, sns_type: str, unit_code: str) -> str:
        """Get unit from unit matrix. Raise DeviceLogicError if missing."""
        try:
            return self.UNIT_MAP[sns_type][unit_code]
        except KeyError as err:
            raise DeviceLogicError(
                f"Unknown unit, device {self.name} sent: '{sns_type}' "
                f"with code: '{unit_code}', that is missing in UNIT_MAP."
            ) from err

    @property
    @abstractmethod
    def name(self) -> str:
        """Return device's name."""

    @property
    @abstractmethod
    def location(self) -> str:
        """Return device's location."""

    @property
    @abstractmethod
    def manufacturer(self) -> str:
        """Return device's manufacturer."""

    @property
    @abstractmethod
    def mac_address(self) -> str:
        """Return device's MAC address."""

    @abstractmethod
    async def parse_fresh_data(self, xml_data: str) -> dict:
        """Parse the device-specific XML and return normalized data.

        The returned dictionary must map the parsed data to standard keys,
        with each containing a nested dictionary indexed by the string `item_id`:

        Example output:
        {
            "temperature": {"1": 25.4, "2": 26.1},
            "switch": {"1": 1, "2": 0}
        }

        If a specific data type is not present on the device, its key should map to an empty dictionary.
        """

    @abstractmethod
    def get_supported_buttons(self) -> list[dict[str, Any]]:
        """Return the configuration data for buttons.

        Expected dictionary structure:
        {
            "cmd": str,
            "name": str, # Fallback name
            "translation": str (Optional), # Key in strings.json
            "placeholder": dict[str, str] (Optional), # Translation formatting vars
            "use_custom_name": bool (Optional), # If True, 'name' is forced and translation ignored
            "icon": str (Optional) # e.g. mdi:gesture-tap-button
        }
        """

    @abstractmethod
    def get_supported_binary_sensors(self) -> list[dict[str, Any]]:
        """Return the configuration data for binary sensors.

        Expected dictionary structure:
        {
            "item_id": str,
            "type": str,
            "name": str, # Fallback name
            "translation": str (Optional),
            "placeholder": dict[str, str] (Optional),
            "use_custom_name": bool (Optional),
            "device_class": str (Optional),
            "icon": str (Optional) # e.g. mdi:radiobox-blank
        }
        """

    @abstractmethod
    def get_supported_numbers(self) -> list[dict[str, Any]]:
        """Return the configuration data for number inputs.

        Expected dictionary structure:
        {
            "item_id": str,
            "category": str,
            "type": str,
            "name": str, # Fallback name
            "translation": str (Optional),
            "placeholder": dict[str, str] (Optional),
            "use_custom_name": bool (Optional),
            "min_value": float | int,
            "max_value": float | int,
            "step": float | int,
            "unit": str (Optional),
            "icon": str (Optional) # e.g. mdi:numeric
        }
        """

    @abstractmethod
    def get_supported_sensors(self) -> list[dict[str, Any]]:
        """Return the configuration data for read-only sensors.

        Expected dictionary structure:
        {
            "item_id": str | int,
            "type": str,
            "name": str, # Fallback name
            "translation": str (Optional),
            "placeholder": dict[str, str] (Optional),
            "use_custom_name": bool (Optional),
            "device_class": str (Optional),
            "state_class": str (Optional),
            "unit": str (Optional),
            "icon": str (Optional) # e.g. mdi:square-wave
        }
        """

    @abstractmethod
    def get_supported_switches(self) -> list[dict[str, Any]]:
        """Return the configuration data for switches.

        Expected dictionary structure:
        {
            "item_id": str,
            "name": str, # Fallback name
            "translation": str (Optional),
            "placeholder": dict[str, str] (Optional),
            "use_custom_name": bool (Optional),
            "icon": str (Optional) # e.g. mdi:power
        }
        """

    @abstractmethod
    def get_supported_selects(self) -> list[dict[str, Any]]:
        """Return the configuration data for select menus.

        Expected dictionary structure:
        {
            "item_id": str,
            "category": str,
            "name": str, # Fallback name
            "options": list[str],
            "translation": str (Optional),
            "placeholder": dict[str, str] (Optional),
            "use_custom_name": bool (Optional),
            "icon": str (Optional) # e.g. mdi:form-dropdown
        }
        """

    @abstractmethod
    async def execute_button_command(self, cmd_type: str) -> None:
        """Execute the command of the button. Router pattern."""

    @abstractmethod
    async def turn_on_switch(self, item_id: str) -> None:
        """Turn on the switch by its id. Router pattern."""

    @abstractmethod
    async def turn_off_switch(self, item_id: str) -> None:
        """Turn off the switch by its id. Router pattern."""

    @abstractmethod
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        """Set the number value by its category and id. Router pattern."""

    @abstractmethod
    def get_select_option(self, category: str, item_id: str) -> str | None:
        """Get the selected option by its category and id. Router pattern."""

    @abstractmethod
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        """Set the selected option by its category and id. Router pattern."""

    @abstractmethod
    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB."""

    @abstractmethod
    def get_location(self) -> str:
        """Return the location of the device.

        Note that this method is used only in a config flow
        that means after user changes the location of the device
        this method will return invalid data.

        These data are from info value but it is loaded only in ctor.
        """

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the device."""

    @abstractmethod
    def get_mac_address(self) -> str:
        """Return the MAC address of the device."""

    @abstractmethod
    def _parse_initial_settings(self) -> None:
        """Parse settings XML for each device.

        Note that this is called only in ctor of the proper device
        and should be a private method.
        """
