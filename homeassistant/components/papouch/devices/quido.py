"""This file contains classes that define Papouch devices.

# TODO: clearing and decreasing counter is not possible in Qudio ETH 3/0B, add it with extra logic ?
"""

import logging
from typing import Any, override
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as defused_ET

from ..APIClient import PapouchApiClient
from .base import PapouchDevice

_LOGGER = logging.getLogger(__name__)


class Quido(PapouchDevice):
    """Represents devices of Quido family."""

    COUNTER_MODES = [
        "Off",
        "Counts descending edges",
        "Counts ascending edges",
        "Counts ascending and descending edges",
    ]

    def __init__(
        self,
        api_client: PapouchApiClient,
        settings: str,
        number_inputs: int,
        number_outputs: int,
        number_temp: int = 1,
    ) -> None:
        """Constructor for Quido device. Downloading the settings during creation."""
        self.name = "Papouch Quido"
        self.manufacturer = "Papouch s.r.o."
        self.api_client = api_client
        self.number_inputs = number_inputs
        self.number_outputs = number_outputs
        self.number_temp = number_temp
        self.counter_states = {}
        self.settings = settings
        self.size_counter_bits = 16

    @override
    def parse_xml(self, xml_data: str) -> dict:
        """Defines parser method for Quido family."""
        root = defused_ET.fromstring(xml_data)
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

    @override
    def get_supported_selects(self) -> list[dict[str, str]]:
        """Return the configuration data for select entities this device supports."""
        return [{"item_id": str(i)} for i in range(1, self.number_inputs + 1)]

    def get_counter_mode(self, item_id: str) -> str:
        """Get the current mode of the counter. Default is OFF."""
        return self.counter_states.get(item_id, self.COUNTER_MODES[0])

    async def set_counter_mode(self, item_id: str, mode: str) -> str | None:
        """Set the new mode of the counter. Return either None or error in string."""
        current_settings = await self.api_client.fetch_settings()

        if current_settings != self.settings:
            # TODO: vymyslet co se ma stat
            pass

        root = defused_ET.fromstring(current_settings)

        item = root.find(f".//set[@box='10']/item[@id='{item_id}']")
        if item is None:
            _LOGGER.error("Item %s not found in settings", item_id)
            return

        try:
            mode_index = self.COUNTER_MODES.index(mode)
        except ValueError:
            _LOGGER.error("Invalid counter mode: %s", mode)
            return

        on_val = item.get("on", "0")
        off_val = item.get("off", "0")
        hide_val = item.get("hide", "0")
        change_val = item.get("change", "0")

        sampl_val = item.get("sampl", "20").zfill(5)
        name_val = item.get("name", "")

        save_root = ET.Element("root")
        ET.SubElement(
            save_root,
            "set",
            box="10",
            num1=str(item_id),
            num2=on_val,
            num3=off_val,
            num4=str(mode_index),
            num5=hide_val,
            num6=change_val,
            num7=sampl_val,
            str1=name_val,
        )

        xml_payload = ET.tostring(save_root, encoding="unicode")

        await self.api_client.send_command_POST(xml_payload)

        self.counter_states[item_id] = mode

    async def switch_to_web_mode(self) -> None:
        """Switch the device network mode to WEB using its current settings."""
        root = defused_ET.fromstring(self.settings)
        box = root.find(".//set[@box='1']")
        if box is None:
            raise ValueError("Network settings (box=1) not found")

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
            ip4=pad_ip(box.get("dip", "0.0.0.0")),
            ip5=pad_ip(box.get("rip", "0.0.0.0")),
            num1=box.get("wport", "80").zfill(5),
            num2=box.get("lport", "10001").zfill(5),
            num3="3",  # WEB mode
            num4=box.get("rport", "0").zfill(5),
            num5=box.get("mport", "502").zfill(5),
            num6=box.get("dhcp", "0"),
            num7=box.get("single", "0"),
            num8=box.get("tcpto", "0").zfill(5),
        )

        xml_payload = ET.tostring(save_root, encoding="unicode")
        await self.api_client.send_command_POST(xml_payload)
