"""This file contains classes that define Papouch devices."""

import logging
from typing import Any, override

import defusedxml.ElementTree as defused_ET

from ..client import PapouchApiClient
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)
TEMP_MULTIPLICATIVE_CONST = 10

# There is only 1 sensor of the temperature and its type is always 4 (temperature)
ITEM_ID = "1"


class TME(PapouchDevice):
    """Represents devices of TME family."""

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
        """Constructor for TME device.

        Note that TME needs info in parameters.
        So creating TME needs using the network even for dummy devices.
        """

        self.info = info

        self._name = self.get_name()
        self._location = self.get_location()
        self.api_client = api_client
        self.units_sensor = []

        self._parse_initial_settings()

    @override
    def parse_xml(self, xml_data: str) -> dict:
        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {"sensor": {}}

        populate = len(self.units_sensor) == 0

        element = find_tag(root, "sns")

        if element is None:
            return parsed_data

        unit_code = element.attrib.get("unit", "0")
        status = element.attrib.get("status", "0")

        if populate:
            self.units_sensor.append({"id": ITEM_ID, "unit": unit_code})
        else:
            self.units_sensor[0]["unit"] = unit_code

        if status in ("1", "4"):  # invalid or ready to measure
            parsed_data["sensor"][ITEM_ID] = None
        else:
            try:
                parsed_data["sensor"][ITEM_ID] = (
                    float(element.attrib.get("val", "0")) / TEMP_MULTIPLICATIVE_CONST
                )
            except ValueError:
                parsed_data["sensor"][ITEM_ID] = None

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
        """Unused in TME."""
        return []

    @override
    def get_supported_binary_sensors(self) -> list[dict[str, Any]]:
        """Unused in TME."""
        return []

    @override
    def get_supported_numbers(self) -> list[dict[str, Any]]:
        """Unused in TME."""
        return []

    @override
    def get_supported_sensors(self) -> list[dict[str, Any]]:
        if not self.units_sensor:
            return []

        unit_map = {"0": "°C", "1": "°F", "2": "K"}

        item_id = str(ITEM_ID)
        unit_code = self.units_sensor[0].get("unit", "0")

        return [
            {
                "item_id": item_id,
                "type": "sensor",
                "name": "Temperature",
                "device_class": "temperature",
                "unit": unit_map.get(unit_code, "°C"),
            }
        ]

    @override
    def get_supported_switches(self) -> list[dict[str, Any]]:
        """Unused in TME."""
        return []

    @override
    def get_supported_selects(self) -> list[dict[str, Any]]:
        """Unused in TME."""
        return []

    @override
    async def execute_button_command(self, cmd_type: str) -> None:
        """Unused in TME."""

    @override
    async def turn_on_switch(self, item_id: str) -> None:
        """Unused in TME."""

    @override
    async def turn_off_switch(self, item_id: str) -> None:
        """Unused in TME."""

    @override
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        """Unused in TME."""

    @override
    def get_select_option(self, category: str, item_id: str) -> str | None:
        """Unused in TME."""
        return None

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        """Unused in TME."""

    @override
    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB using its current settings."""

    @override
    def _parse_initial_settings(self) -> None:
        pass
