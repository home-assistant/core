"""This file contains classes that define Papouch devices."""

import logging
from typing import Any, cast, override

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient, PapouchTransport
from ..exceptions import DeviceParseError
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)
TEMP_MULTIPLICATIVE_CONST = 10

# There is only 1 sensor of the temperature and its type is always 4 (temperature)
ITEM_ID = "1"


class TME(PapouchDevice):
    """Represents devices of TME family."""

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

    def __init__(self, api_client: PapouchTransport, info: str, fresh: str) -> None:
        """Constructor for TME device."""

        self.api_client = cast(PapouchHTTPClient, api_client)

        self.info_root = defused_ET.fromstring(info)
        self.fresh_root = defused_ET.fromstring(fresh)

        self._name = self.get_name()
        self._location = self.get_location()
        self._mac_address = self.get_mac_address()

        self.units_sensor: list[dict[str, str]] = []

        self._parse_initial_settings()

    @override
    async def parse_fresh_data(self, xml_data: str) -> dict:
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
        """Return the name of the device."""
        status = find_tag(self.fresh_root, "status")
        if status is not None:
            return status.attrib.get("mac", "")

        raise DeviceParseError(
            f"The device doesn't have status with MAC address, device: {self.name} ({self.location}) - {self.api_client.ip_address}"
        )

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
        unit_code = "0"
        if self.units_sensor:
            unit_code = self.units_sensor[0].get("unit", "0")

        return [
            {
                "item_id": ITEM_ID,
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
        """Unused in TME."""

    @override
    def _parse_initial_settings(self) -> None:
        pass


async def async_setup_tme(transport: PapouchTransport) -> TME | None:
    """Async factory for TME device."""
    fresh = await transport.fetch_data()
    info = await transport.fetch_info()

    return TME(transport, info, fresh)
