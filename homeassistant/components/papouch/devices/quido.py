"""This file contains classes that define Papouch devices.

# TODO: clearing and decreasing counter is not possible in Qudio ETH 3/0B, add it with extra logic ?
"""

from typing import Any, override

import defusedxml.ElementTree as ET

from ..APIClient import PapouchApiClient
from .base import PapouchDevice


class Quido(PapouchDevice):
    """Represents devices of Quido family."""

    def __init__(
        self,
        api_client: PapouchApiClient,
        number_inputs: int,
        number_outputs: int,
        number_temp: int = 1,
    ) -> None:
        """Constructor for Quido device."""
        self.name = "Papouch Quido"
        self.manufacturer = "Papouch s.r.o."
        self.api_client = api_client
        self.number_inputs = number_inputs
        self.number_outputs = number_outputs
        self.number_temp = number_temp

    @override
    def parse_xml(self, xml_data: str) -> dict:
        """Defines parser method for Quido family."""
        root = ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {
            "temp": {},
            "din": {},
            "dout": {},
            "din_cnt": {},
        }

        for element in root:
            item_id = element.attrib.get("id")

            if element.tag == "temp":
                val_str = element.attrib.get("val", "0")
                parsed_data["temp"][item_id] = float(val_str)

            elif element.tag == "dout":
                val_str = element.attrib.get("val", "0")
                parsed_data["dout"][item_id] = int(val_str)

            elif element.tag == "din":
                parsed_data["din"][item_id] = int(element.attrib.get("val", "0"))
                parsed_data["din_cnt"][item_id] = int(element.attrib.get("cnt", "0"))

        return parsed_data

    async def connect_all_coils(self) -> None:
        """Command for connecting all the coils."""
        await self._send_command("S")

    async def disconnect_all_coils(self) -> None:
        """Command for disconnecting all the coils."""
        await self._send_command("R")

    async def reset_all_counters(self) -> None:
        """Command for resetting all the counters."""
        await self._send_command("C")

    async def decrease_value_counter(self, item_id: str, value: int) -> None:
        """Command for decreasing specific counter."""
        await self._send_command("c", item_id, value)

    async def turn_on_coil(self, item_id: str) -> None:
        """Command for turning on the coil by its id."""
        await self._send_command("s", item_id)

    async def turn_off_coil(self, item_id: str) -> None:
        """Command for turning off the coil by its id."""
        await self._send_command("r", item_id)

    async def _send_command(
        self, cmd_type: str, item_id: str | None = None, counter: str | None = None
    ) -> None:

        raw_params = {
            "type": cmd_type,
            "id": item_id,
            "cnt": counter,
        }
        # adding the optional parameters
        params = {key: value for key, value in raw_params.items() if value is not None}

        await self.api_client.send_command_GET(params)

    @override
    def get_supported_buttons(self) -> list[dict[str, str]]:
        """Return the configuration data for buttons that supports Quido."""
        return [
            # TODO: clearing and decreasing counter is not possible in Qudio ETH 3/0B add it with extra logic
            {"name": "Connect all coils", "cmd": "connect_all_coils"},
            {"name": "Disconnect all coils", "cmd": "disconnect_all_coils"},
            {"name": "Reset all counters", "cmd": "reset_all_counters"},
        ]

    @override
    def get_supported_binary_sensors(self) -> list[dict[str, str]]:
        """Return the configuration data for binary sensors that supports Quido."""
        return [{"item_id": str(i)} for i in range(1, self.number_inputs + 1)]

    @override
    def get_supported_numbers(self) -> list[dict[str, str]]:
        """Return the configuration data for number inputs (decreasing counters) that supports Quido."""
        return [{"item_id": str(i)} for i in range(1, self.number_inputs + 1)]

    @override
    def get_supported_sensors(self) -> list[dict[str, str]]:
        """Return the configuration data for read-only sensors that supports Quido."""
        sensors = []

        for i in range(1, self.number_temp + 1):
            sensors.append({"item_id": str(i), "type": "temp"})  # noqa: PERF401

        for i in range(1, self.number_inputs + 1):
            sensors.append({"item_id": str(i), "type": "counter"})  # noqa: PERF401

        return sensors

    @override
    def get_supported_switches(self) -> list[dict[str, str]]:
        """Return the configuration data for switches this device supports."""
        return [{"item_id": str(i)} for i in range(1, self.number_outputs + 1)]
