"""This file contains classes that define Papouch devices."""

import logging
from typing import Any, override

import defusedxml.ElementTree as defused_ET

from ..APIClient import PapouchApiClient
from ..const import DATA_SENSOR
from .base import PapouchDevice

_LOGGER = logging.getLogger(__name__)


class TH2E(PapouchDevice):
    """Represents devices of TH2E family."""

    def __init__(self, api_client: PapouchApiClient, info: str) -> None:
        """Constructor for TH2E device. Downloading the settings before creation."""
        self.name = "Papouch TH2E"
        self.manufacturer = "Papouch s.r.o."
        self.api_client = api_client
        self.units_sensors = []
        self.info = info

        self._parse_initial_settings()

    @override
    def parse_xml(self, xml_data: str) -> dict:
        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {DATA_SENSOR: {}}

        populate = len(self.units_sensors) == 0

        for element in root.findall("sns"):
            item_id = element.attrib.get("id")
            sns_type = element.attrib.get("type")
            unit_code = element.attrib.get("unit", "0")
            status = element.attrib.get("status", "0")

            if populate:
                self.units_sensors.append(
                    {"id": item_id, "type": sns_type, "unit": unit_code}
                )

            if status in ("1", "4"):  # invalid or ready to measure
                parsed_data[DATA_SENSOR][item_id] = None
            else:
                parsed_data[DATA_SENSOR][item_id] = float(
                    element.attrib.get("val", "0")
                )

        return parsed_data

    @override
    def get_location(self) -> str:
        """Return the location of the device."""
        root = defused_ET.fromstring(self.info)
        heartbeat = root.find("heartbeat")
        return heartbeat.attrib.get("location")

    @override
    def get_name(self) -> str:
        """Return the name of the device."""
        root = defused_ET.fromstring(self.info)
        heartbeat = root.find("heartbeat")
        return heartbeat.attrib.get("device")

    @override
    def get_supported_buttons(self) -> list[dict[str, Any]]:
        """Unused in TH2E."""
        return []

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

        for sns in self.units_sensors:
            item_id = sns["id"]
            sns_type = sns["type"]
            unit_code = sns["unit"]

            if sns_type == "1":
                sensors.append(
                    {
                        "item_id": item_id,
                        "type": DATA_SENSOR,
                        "name": "Temperature",
                        "device_class": "temperature",
                        "unit": unit_map.get(unit_code, "°C"),
                    }
                )
            elif sns_type == "2":
                sensors.append(
                    {
                        "item_id": item_id,
                        "type": DATA_SENSOR,
                        "name": "Humidity",
                        "device_class": "humidity",
                        "unit": "%",
                    }
                )
            elif sns_type == "3":
                sensors.append(
                    {
                        "item_id": item_id,
                        "type": DATA_SENSOR,
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
        """Unused in TH2E."""
        return []

    @override
    async def execute_button_command(self, cmd_type: str) -> None:
        """Unused in TH2E."""
        return []

    @override
    async def turn_on_switch(self, item_id: str) -> None:
        """Unused in TH2E."""
        return []

    @override
    async def turn_off_switch(self, item_id: str) -> None:
        """Unused in TH2E."""
        return []

    @override
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        """Unused in TH2E."""
        return []

    @override
    def get_select_option(self, category: str, item_id: str) -> str | None:
        """Unused in TH2E."""
        return []

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        """Unused in TH2E."""
        return []

    @override
    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB using its current settings."""
        # root = defused_ET.fromstring(self.settings)
        # box = root.find(".//set[@box='1']")
        # if box is None:
        #     raise ValueError("Network settings not found")

        # def pad_ip(ip_str: str) -> str:
        #     return ".".join(part.zfill(3) for part in ip_str.split("."))

        # save_root = ET.Element("root")
        # ET.SubElement(
        #     save_root,
        #     "set",
        #     box="1",
        #     ip1=pad_ip(box.get("ip", "0.0.0.0")),
        #     ip2=pad_ip(box.get("mask", "0.0.0.0")),
        #     ip3=pad_ip(box.get("gate", "0.0.0.0")),
        #     ip4=pad_ip(box.get("dip", "0.0.0.0")),
        #     ip5=pad_ip(box.get("rip", "0.0.0.0")),
        #     num1=box.get("wport", "80").zfill(5),
        #     num2=box.get("lport", "10001").zfill(5),
        #     num3="3",
        #     num4=box.get("rport", "0").zfill(5),
        #     num5=box.get("mport", "502").zfill(5),
        #     num6=box.get("dhcp", "0"),
        #     num7=box.get("single", "0"),
        #     num8=box.get("tcpto", "0").zfill(5),
        # )

        # xml_payload = ET.tostring(save_root, encoding="unicode")
        # await self.api_client.send_command_POST(xml_payload)

    @override
    def _parse_initial_settings(self) -> None:
        pass
        # if not self.settings:
        #     return

        # try:
        #     root = defused_ET.fromstring(self.settings)
        #     for item in root.findall(".//set[@box='10']/item"):
        #         if (item_id := item.get("id")) is None:
        #             continue

        #         mode_index_str = item.get("cnt", "0")

        #         try:
        #             mode_index = int(mode_index_str)
        #             if 0 <= mode_index < len(self.COUNTER_MODES):
        #                 self.counter_states[item_id] = self.COUNTER_MODES[mode_index]
        #         except ValueError:
        #             _LOGGER.error(
        #                 "Invalid mode index for item %s: %s", item_id, mode_index_str
        #             )

        #     box_elem = root.find(".//set[@box='8']")
        #     unit = box_elem.get("units")
        #     if unit == "C":
        #         self.temperature_unit = "°C"
        #     elif unit == "F":
        #         self.temperature_unit = "°F"
        #     else:
        #         self.temperature_unit = "K"

        # except (defused_ET.ParseError, ValueError, TypeError) as err:
        #     _LOGGER.error("Failed to parse initial settings: %s", err)
