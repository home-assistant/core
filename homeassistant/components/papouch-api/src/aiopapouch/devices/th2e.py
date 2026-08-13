"""This file contains definition of the TH2E device."""

import logging
from typing import Any, cast, override
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient, PapouchTransport
from ..exceptions import DeviceLogicError, DeviceParseError, DeviceResponseError
from .base import HTTPMixin, PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)


class TH2E(PapouchDevice, HTTPMixin):
    """Represents TH2E device."""

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

    def __init__(self, api_client: PapouchTransport, settings: str, info: str) -> None:
        """Constructor for TH2E device."""

        super().__init__()

        self.api_client = cast(PapouchHTTPClient, api_client)

        self.info_root = defused_ET.fromstring(info)
        self.settings_root = defused_ET.fromstring(settings)

        self._name = self.get_name()
        self._location = self.get_location()
        self._mac_address = self.get_mac_address()

        self.sensors: dict[str, dict[str, str]] = {}
        self.sensor_type = 0

    @override
    async def parse_fresh_data(self, xml_data: str) -> dict:
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

        self.sensor_type = int(status_tag.attrib.get("typesens", "0"))

        for element in root.iter():
            if not element.tag.endswith("sns"):
                continue

            item_id = element.attrib.get("id")
            sns_type = element.attrib.get("type")
            unit_code = element.attrib.get("unit", "0")

            # unit 3 means percentage but in global unit map it would be 1
            if unit_code == "3":
                unit_code = "0"

            status = element.attrib.get("status", "0")

            self.sensors[item_id] = {
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
        box = self.settings_root.find(".//set[@box='12']")

        if box is not None:
            return str(box.attrib.get("mac", ""))

        raise DeviceParseError(
            f"The device doesn't have box 12 with MAC address, device: {self.name} ({self.location}) - {self.api_client.ip_address}"
        )

    @override
    def get_supported_buttons(self) -> list[dict[str, Any]]:
        """Unused in TH2E."""
        return [{"translation": "set_sensor", "cmd": "set_sensor"}]

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

        for sns in self.sensors.values():
            item_id = sns["id"]
            sns_type = sns["type"]
            unit_code = sns["unit"]

            match sns_type:
                case self.TEMPERATURE_SNS_TYPE:
                    sensors.append(
                        {
                            "item_id": item_id,
                            "type": "sensor",
                            "translation": "sensor_temperature",
                            "device_class": "temperature",
                            "state_class": "measurement",
                            "unit": self._get_unit(sns_type, unit_code),
                        }
                    )

                case self.HUMIDITY_SNS_TYPE:
                    sensors.append(
                        {
                            "item_id": item_id,
                            "type": "sensor",
                            "translation": "sensor_humidity",
                            "device_class": "humidity",
                            "state_class": "measurement",
                            "unit": self._get_unit(sns_type, unit_code),
                        }
                    )

                case self.DEW_POINT_SNS_TYPE:
                    sensors.append(
                        {
                            "item_id": item_id,
                            "type": "sensor",
                            "translation": "sensor_dew_point",
                            "device_class": "temperature",
                            "state_class": "measurement",
                            "unit": self._get_unit(sns_type, unit_code),
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
                "translation": "sensor_type",
                "placeholder": {"placeholder": "Sensor"},
                "options": self.SENSOR_TYPES,
            }
        ]

    @override
    async def execute_button_command(self, cmd_type: str) -> None:
        if cmd_type != "set_sensor":
            raise DeviceLogicError(
                f"Unsupported command: {cmd_type}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        self.sensor_type = await self._get_sensor_type()
        await self._set_sensor_type(self.sensor_type)

    async def _get_sensor_type(self) -> int:
        request = '<root><set box="19" num1="00001" /></root>'
        response = await self.api_client.write_command(
            request, f"{self.name} ({self.location})"
        )

        return self._check_sensor_response(
            response,
            expected_status="4",
            action_msg="fetching the type of the sensor",
        )

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

        final_response = await self.api_client.write_command(
            xml_payload, f"{self.name} ({self.location})"
        )

        self._check_sensor_response(
            final_response,
            expected_status="2",
            action_msg="setting the type of the sensor",
        )

    def _check_sensor_response(
        self, response_text: str, expected_status: str, action_msg: str
    ) -> int:
        try:
            root = defused_ET.fromstring(response_text)
            result_tag = find_tag(root, "result")

            if result_tag is None:
                raise DeviceParseError(
                    f"Response doesn't have result tag!, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
                )

            if result_tag.attrib.get("status") != expected_status:
                raise DeviceResponseError(
                    f"{self.name} ({self.location}) - {self.api_client.ip_address} returned an error while {action_msg}, whole response: {response_text}"
                )

            return int(result_tag.attrib.get("typesens", "0"))

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
            return self.SENSOR_TYPES[self.sensor_type]
        return None

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        type_idx = self.SENSOR_TYPES.index(option)
        await self._set_sensor_type(type_idx)
        self.sensor_type = type_idx

    @override
    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB using its current settings."""
        box = self.settings_root.find(".//set[@box='1']")
        if box is None:
            raise DeviceParseError(
                f"Box for network mode is not found, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        def pad_ip(ip_str: str) -> str:
            return ".".join(part.zfill(3) for part in ip_str.split("."))

        save_root = ET.Element("root")
        ET.SubElement(
            save_root,
            "set",
            box="1",
            ip1=pad_ip(box.get("ip", "0.0.0.0")),
            ip2=pad_ip(box.get("mask", "0.0.0.0")),
            ip3=pad_ip(box.get("gate", "0.0.0.0")),
            ip5=pad_ip(box.get("dip", "0.0.0.0")),
            num2=box.get("wport", "80").zfill(5),
            num4="3",
            num5=box.get("com", "0"),
            num7=box.get("mport", "502").zfill(5),
            num1=box.get("lport", "10001").zfill(5),
            ip4=pad_ip(box.get("rip", "0.0.0.0")),
            num3=box.get("rport", "0").zfill(5),
        )

        xml_payload = ET.tostring(save_root, encoding="unicode")
        response = await self.api_client.write_command(
            xml_payload, f"{self.name} ({self.location})"
        )

        self._check_sensor_response(response, "2", "setting to WEB mode")

    @override
    def _parse_initial_settings(self) -> None:
        pass


async def async_setup_th2e(transport: PapouchTransport) -> TH2E | None:
    """Async factory for TH2E device."""
    settings = await transport.fetch_settings()
    info = await transport.fetch_info()

    return TH2E(transport, settings, info)
