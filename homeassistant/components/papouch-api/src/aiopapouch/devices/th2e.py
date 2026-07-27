"""This file contains definition of the TH2E device."""

import logging
from typing import Any, override

import defusedxml.ElementTree as defused_ET

from ..client import PapouchApiClient
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)


class TH2E(PapouchDevice):
    """Represents devices of TH2E family."""

    @property
    def name(self) -> str:
        """Return device's name."""
        return self._name

    @property
    def location(self) -> str:
        """Return device's location."""
        return self._location

    @property
    def manufacturer(self) -> str:
        """Return device's manufacturer."""
        return "Papouch s.r.o."

    def __init__(self, api_client: PapouchApiClient, info: str) -> None:
        """Constructor for TH2E device.

        Note that TH2E needs info in parameters.
        So creating TH2E needs using the network even for dummy devices.
        """

        self.info = info

        self._name = self.get_name()
        self._location = self.get_location()
        self.api_client = api_client
        self.units_sensors = {}

        self.parse_xml(self.info)
        self._parse_initial_settings()

    @override
    def parse_xml(self, xml_data: str) -> dict:
        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {"sensor": {}}

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
        root = defused_ET.fromstring(self.info)
        heartbeat = find_tag(root, "heartbeat")
        return heartbeat.attrib.get("location") if heartbeat is not None else ""

    @override
    def get_name(self) -> str:
        """Return the name of the device."""
        root = defused_ET.fromstring(self.info)
        heartbeat = find_tag(root, "heartbeat")
        return heartbeat.attrib.get("device") if heartbeat is not None else ""

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

    @override
    def _parse_initial_settings(self) -> None:
        pass
