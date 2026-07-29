"""This file contains definition of the TH2E device."""

import logging
from typing import Any, override
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as defused_ET

from ..client import PapouchApiClient
from ..exceptions import DeviceLogicError, DeviceParseError, DeviceResponseError
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)


class TH2E(PapouchDevice):
    """Represents TH2E device."""

    SENSOR_TYPES = [
        "Unused",
        "Temperature / Humidity (TH15)",
        "Temperature (DS)",
        "Temperature / Humidity (TH3x)",
        "Temperature (TMP)",
    ]

    @override
    @property
    def name(self) -> str:
        """Return device's name."""
        return self._name

    @override
    @property
    def location(self) -> str:
        """Return device's location."""
        return self._location

    @override
    @property
    def manufacturer(self) -> str:
        """Return device's manufacturer."""
        return "Papouch s.r.o."

    @override
    @property
    def mac_address(self) -> str:
        """Return device's MAC address."""
        return self._mac_address

    def __init__(self, api_client: PapouchApiClient, settings: str, info: str) -> None:
        """Constructor for TH2E device."""
        self.api_client = api_client

        self.info_root = defused_ET.fromstring(info)
        self.settings_root = defused_ET.fromstring(settings)

        self._name = self.get_name()
        self._location = self.get_location()
        self._mac_address = self.get_mac_address()

        self.units_sensors: dict[str, dict[str, str]] = {}
        self.type_sensor = 0

    @override
    def parse_xml(self, xml_data: str) -> dict:
        """Parse XML data into dictionary to feed the coordinator.

        Note that it also sets the type of the sensor. (Global one)
        """

        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {"sensor": {}}

        status_tag = find_tag(root, "status")

        if status_tag is None:
            raise DeviceParseError(
                f"The device doesn't have box status tag in fresh.xml, device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        self.type_sensor = int(status_tag.attrib.get("typesens", ""))

        for element in root.iter():
            if not element.tag.endswith("sns"):
                continue

            item_id = element.attrib.get("id")
            sns_type = element.attrib.get("type")
            unit_code = element.attrib.get("unit", "0")
            status = element.attrib.get("status", "0")

            self.units_sensors[item_id] = {
                "id": item_id,
                "type": sns_type,
                "unit": unit_code,
            }

            if status in ("1", "4"):
                parsed_data["sensor"][item_id] = None
            else:
                parsed_data["sensor"][item_id] = float(element.attrib.get("val", "0"))

        return parsed_data

    @override
    def get_location(self) -> str:
        """Return the location of the device."""
        heartbeat = find_tag(self.info_root, "heartbeat")
        if heartbeat is not None:
            return heartbeat.attrib.get("location", "")
        return ""

    @override
    def get_name(self) -> str:
        """Return the name of the device."""
        heartbeat = find_tag(self.info_root, "heartbeat")
        if heartbeat is not None:
            return heartbeat.attrib.get("device", "")
        return ""

    @override
    def get_mac_address(self) -> str:
        """Return the MAC address of the device."""
        box = self.settings_root.find(
            ".//{http://www.papouch.com/xml/th2e/set}set[@box='12']"
        )

        if box is not None:
            return str(box.attrib.get("mac", ""))

        raise DeviceParseError(
            f"The device doesn't have box 12 with MAC address, device: {self.name} ({self.location}) - {self.api_client.ip_address}"
        )

    @override
    def get_supported_buttons(self) -> list[dict[str, Any]]:
        """Unused in TH2E."""
        return [{"name": "Set sensor automatically", "cmd": "set_sensor"}]

    @override
    def get_supported_binary_sensors(self) -> list[dict[str, Any]]:
        """Unused in TH2E."""
        return []

    @override
    def get_supported_numbers(self) -> list[dict[str, Any]]:
        """Unused in TH2E."""
        return []

    @override
    def get_supported_sensors(self) -> list[dict[str, Any]]:
        sensors = []
        unit_map = {"0": "°C", "1": "°F", "2": "K"}

        for sns in self.units_sensors.values():
            item_id = sns["id"]
            sns_type = sns["type"]
            unit_code = sns["unit"]

            if sns_type == "1":
                sensors.append(
                    {
                        "item_id": item_id,
                        "type": "sensor",
                        "name": "Temperature",
                        "device_class": "temperature",
                        "unit": unit_map.get(unit_code, "°C"),
                    }
                )
            elif sns_type == "2":
                sensors.append(
                    {
                        "item_id": item_id,
                        "type": "sensor",
                        "name": "Humidity",
                        "device_class": "humidity",
                        "unit": "%",
                    }
                )
            elif sns_type == "3":
                sensors.append(
                    {
                        "item_id": item_id,
                        "type": "sensor",
                        "name": "Dew Point",
                        "device_class": "temperature",
                        "unit": unit_map.get(unit_code, "°C"),
                    }
                )

        return sensors

    @override
    def get_supported_switches(self) -> list[dict[str, Any]]:
        """Unused in TH2E."""
        return []

    @override
    def get_supported_selects(self) -> list[dict[str, Any]]:
        """Get supported modes of the sensors."""
        return [
            {
                "item_id": 1,
                "category": "sensor_type",
                "name": "Sensor type:",
                "options": self.SENSOR_TYPES,
            }
        ]

    @override
    async def execute_button_command(self, cmd_type: str) -> None:
        if cmd_type != "set_sensor":
            raise DeviceLogicError(
                f"Unsupported command: {cmd_type}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        self.type_sensor = await self._get_sensor_type()
        await self._set_sensor_type(self.type_sensor)

    async def _get_sensor_type(self) -> int:
        request = '<root><set box="19" num1="00001" /></root>'
        response = await self.api_client.send_command_POST(
            request, f"{self.name} ({self.location})"
        )

        return self._check_response_fetch_sens(response)

    async def _set_sensor_type(self, type_idx: int) -> None:
        settings = await self.api_client.fetch_settings()

        try:
            settings_root = defused_ET.fromstring(settings)
        except defused_ET.ParseError as exception:
            raise DeviceParseError(
                f"Invalid settings XML: {exception}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from exception

        def format_str_val(val: str) -> str:
            clean_val = val.removesuffix(".0")
            return clean_val.rjust(10, " ")

        set_attrs = {
            "box": "9",
            "num1": str(type_idx),
            "num2": "0",
            "str1": format_str_val("-40"),
            "str2": format_str_val("125"),
            "str3": format_str_val("0"),
            "num3": "00020",
            "str4": format_str_val("0"),
            "str5": format_str_val("100"),
            "str6": format_str_val("0"),
            "num4": "00001",
            "str7": format_str_val("-40"),
            "str8": format_str_val("125"),
            "str9": format_str_val("0"),
            "num5": "00001",
        }

        num2_val = 0

        for i in range(1, 4):
            item = None
            for element in settings_root.iter():
                if element.tag.endswith("sns") and element.attrib.get("id") == str(i):
                    item = element
                    break

            if item is None:
                continue

            if item.get("sns2mem", "0") == "1":
                num2_val += 1 << (i + 3)

            str_base = (i - 1) * 3

            if "min" in item.attrib:
                set_attrs[f"str{str_base + 1}"] = format_str_val(item.attrib["min"])
            if "max" in item.attrib:
                set_attrs[f"str{str_base + 2}"] = format_str_val(item.attrib["max"])
            if "hyst" in item.attrib:
                set_attrs[f"str{str_base + 3}"] = format_str_val(item.attrib["hyst"])
            if "memhyst" in item.attrib:
                set_attrs[f"num{i + 2}"] = item.attrib["memhyst"].zfill(5)

        set_attrs["num2"] = str(num2_val)

        save_root = ET.Element("root", xmlns="http://www.papouch.com/xml/th2e/save")
        ET.SubElement(save_root, "set", attrib=set_attrs)

        xml_payload = ET.tostring(save_root, encoding="unicode")

        final_response = await self.api_client.send_command_POST(
            xml_payload, f"{self.name} ({self.location})"
        )
        self._check_response_post_sens(final_response)

    def _check_response_fetch_sens(self, response_text: str) -> int:
        try:
            root = defused_ET.fromstring(response_text)
            result_tag = find_tag(root, "result")

            if result_tag is None:
                raise DeviceParseError(
                    f"Response doesn't have result tag!, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
                )

            if result_tag.attrib.get("status") != "4":
                raise DeviceResponseError(
                    f"{self.name} ({self.location}) - {self.api_client.ip_address} returned a status error while fetching the type of the sensor, whole response: {response_text}"
                )

            return int(result_tag.attrib.get("typesens", "0"))

        except defused_ET.ParseError as exception:
            raise DeviceParseError(
                f"Invalid XML response from device: {exception}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from exception

    def _check_response_post_sens(self, response_text: str) -> None:
        try:
            root = defused_ET.fromstring(response_text)
            result_tag = find_tag(root, "result")

            if result_tag is None:
                raise DeviceParseError(
                    f"Response doesn't have result tag!, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
                )

            if result_tag.attrib.get("status") != "2":
                raise DeviceResponseError(
                    f"{self.name} ({self.location}) - {self.api_client.ip_address} returned an error while settings the type of the sensor, whole response: {response_text}"
                )

        except defused_ET.ParseError as exception:
            raise DeviceParseError(
                f"Invalid XML response from device: {exception}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from exception

    @override
    async def turn_on_switch(self, item_id: str) -> None:
        """Unused in TH2E."""
        return

    @override
    async def turn_off_switch(self, item_id: str) -> None:
        """Unused in TH2E."""
        return

    @override
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        """Unused in TH2E."""
        return

    @override
    def get_select_option(self, category: str, item_id: str) -> str | None:
        if category == "sensor_type":
            return self.SENSOR_TYPES[self.type_sensor]
        return None

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        type_idx = self.SENSOR_TYPES.index(option)
        await self._set_sensor_type(type_idx)
        self.type_sensor = type_idx

    @override
    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB using its current settings."""

    @override
    def _parse_initial_settings(self) -> None:
        pass
