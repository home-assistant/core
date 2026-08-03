"""This file contains definition of the QuidoETH device."""

from abc import ABC, abstractmethod
import logging
from typing import Any, cast, override
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient, PapouchTransport
from ..exceptions import DeviceLogicError, DeviceParseError, DeviceResponseError
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)
ERROR_STATUS = "0"


class QuidoBase(PapouchDevice, ABC):
    """Base class for all Quido devices containing shared entity logic."""

    COUNTER_MODES = [
        "Off",
        "Counts descending edges",
        "Counts ascending edges",
        "Counts ascending and descending edges",
    ]

    def __init__(self) -> None:
        """Constructor for the base of the Quido."""

        # These variables should be populated by the child classes
        self.api_client: PapouchTransport
        self.number_inputs = -1
        self.number_outputs = -1
        self.number_temp = 1
        self.counter_states: dict[str, str] = {}
        self.temperature_unit = "°C"
        self.size_counter_bits = -1
        self._name = ""
        self._location = ""
        self._mac_address = ""

    # These methods are the same for every Quido device:

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

    @override
    def get_supported_buttons(self) -> list[dict[str, Any]]:
        """Return the configuration data for buttons that supports Quido."""
        return [
            {"name": "Connect all coils", "cmd": "connect_all_coils"},
            {"name": "Disconnect all coils", "cmd": "disconnect_all_coils"},
            {"name": "Reset all counters", "cmd": "reset_all_counters"},
        ]

    @override
    def get_supported_binary_sensors(self) -> list[dict[str, Any]]:
        """Return the configuration data for binary sensors."""
        return [
            {
                "item_id": str(i),
                "type": "input",
                "name": f"Input {i}",
            }
            for i in range(1, self.number_inputs + 1)
        ]

    @override
    def get_supported_numbers(self) -> list[dict[str, Any]]:
        """Return the configuration data for number entities."""
        result = [
            {
                "item_id": str(i),
                "category": "decrease_counter",
                "type": "counter",
                "name": f"Decrease counter {i} by",
                "min_value": 0,
                "max_value": (2**self.size_counter_bits) - 1,
                "step": 1,
            }
            for i in range(1, self.number_inputs + 1)
        ]
        result.extend(
            {
                "item_id": str(i),
                "category": f"output_{action}_time",
                "type": "switch",
                "name": f"Output {i} {action} for duration (s)",
                "min_value": 0.5,
                "max_value": 127.5,
                "step": 0.5,
                "unit": "s",
                "mode": "box",
            }
            for i in range(1, self.number_outputs + 1)
            for action in ("on", "off")
        )

        return result

    @override
    def get_supported_sensors(self) -> list[dict[str, Any]]:
        """Return the configuration data for read-only sensors."""
        sensors = [
            {
                "item_id": str(i),
                "type": "temperature",
                "name": f"Temperature {i}",
                "unit": self.temperature_unit,
            }
            for i in range(1, self.number_temp + 1)
        ]

        sensors.extend(
            [
                {
                    "item_id": str(i),
                    "type": "counter",
                    "name": f"Input {i} Count",
                    "state_class": "total_increasing",
                    "unit": "pulses",
                }
                for i in range(1, self.number_inputs + 1)
            ]
        )

        return sensors

    @override
    def get_supported_switches(self) -> list[dict[str, Any]]:
        """Return the configuration data for switches."""
        return [
            {
                "item_id": str(i),
                "name": f"Output {i}",
            }
            for i in range(1, self.number_outputs + 1)
        ]

    @override
    def get_supported_selects(self) -> list[dict[str, Any]]:
        """Return the configuration data for selects."""
        selects = []
        for i in range(1, self.number_inputs + 1):
            selects.append(  # noqa: PERF401
                {
                    "item_id": str(i),
                    "category": "counter_mode",
                    "name": f"Counter {i} Mode",
                    "options": self.COUNTER_MODES,
                }
            )
        return selects

    @override
    async def execute_button_command(self, cmd_type: str) -> None:
        """Route the button press to the correct method."""
        if cmd_type == "connect_all_coils":
            await self._connect_all_coils()
        elif cmd_type == "disconnect_all_coils":
            await self._disconnect_all_coils()
        elif cmd_type == "reset_all_counters":
            await self._reset_all_counters()
        else:
            raise DeviceLogicError(
                f"Unsupported command: {cmd_type}, in the device: {self.name} ({self.location})"
            )

    @override
    async def turn_on_switch(self, item_id: str) -> None:
        """Turn on the switch by its id."""
        await self._turn_on_coil(item_id)

    @override
    async def turn_off_switch(self, item_id: str) -> None:
        """Turn off the switch by its id."""
        await self._turn_off_coil(item_id)

    # These are the methods all of the children should implement

    @abstractmethod
    async def _connect_all_coils(self) -> None:
        pass

    @abstractmethod
    async def _disconnect_all_coils(self) -> None:
        pass

    @abstractmethod
    async def _reset_all_counters(self) -> None:
        pass

    @abstractmethod
    async def _turn_on_coil(self, item_id: str) -> None:
        pass

    @abstractmethod
    async def _turn_off_coil(self, item_id: str) -> None:
        pass

    @abstractmethod
    async def _decrease_value_counter(self, item_id: str, value: int) -> None:
        pass


class QuidoETH(QuidoBase):
    """Represents devices of Quido family."""

    api_client: PapouchHTTPClient

    def __init__(self, api_client: PapouchTransport, settings: str, info: str) -> None:
        """Constructor for Quido device."""

        super().__init__()
        self.api_client = cast(PapouchHTTPClient, api_client)

        self.info_root = defused_ET.fromstring(info)
        self.settings_root = defused_ET.fromstring(settings)

        self._name = self.get_name()
        self._location = self.get_location()
        self._mac_address = self.get_mac_address()

        self.number_inputs = -1
        self.number_outputs = -1
        self.number_temp = 1
        self.counter_states: dict[str, str] = {}
        self.size_counter_bits = 16
        self.temperature_unit = "°C"  # default

        self._parse_initial_settings()

    @override
    def parse_fresh_data(self, xml_data: str) -> dict:
        """Defines parser method for QuidoETH."""
        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {
            "temperature": {},
            "input": {},
            "switch": {},
            "counter": {},
        }

        for element in root:
            item_id = element.attrib.get("id")

            if element.tag == "temp":
                val_str = element.attrib.get("val", "0")
                if val_str == "":
                    val_str = 0
                parsed_data["temperature"][item_id] = float(val_str)

            elif element.tag == "dout":  # codespell:ignore dout
                val_str = element.attrib.get("val", "0")
                parsed_data["switch"][item_id] = int(val_str)

            elif element.tag == "din":
                parsed_data["input"][item_id] = int(element.attrib.get("val", "0"))
                parsed_data["counter"][item_id] = int(element.attrib.get("cnt", "0"))

        return parsed_data

    @override
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        if category == "decrease_counter":
            await self._decrease_value_counter(item_id, int(value))
        elif category == "output_on_time":
            time_units = max(1, min(255, int(value * 2)))
            await self._send_command("s", item_id=item_id, time=str(time_units))
        elif category == "output_off_time":
            time_units = max(1, min(255, int(value * 2)))
            await self._send_command("r", item_id=item_id, time=str(time_units))

    @override
    def get_select_option(self, category: str, item_id: str) -> str | None:
        """Return selected option by its id."""
        if category == "counter_mode":
            return self._get_counter_mode(item_id)
        return None

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        """Set selected option by its id."""
        if category == "counter_mode":
            await self._set_counter_mode(item_id, option)

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
            ip4=pad_ip(box.get("dip", "0.0.0.0")),
            ip5=pad_ip(box.get("rip", "0.0.0.0")),
            num1=box.get("wport", "80").zfill(5),
            num2=box.get("lport", "10001").zfill(5),
            num3="3",
            num4=box.get("rport", "0").zfill(5),
            num5=box.get("mport", "502").zfill(5),
            num6=box.get("dhcp", "0"),
            num7=box.get("single", "0"),
            num8=box.get("tcpto", "0").zfill(5),
        )

        xml_payload = ET.tostring(save_root, encoding="unicode")
        response = await self.api_client.write_command(
            xml_payload, f"{self.name} ({self.location})"
        )
        self._check_response(response)

    @override
    async def _connect_all_coils(self) -> None:
        """Command for connecting all the coils."""
        await self._send_command("S")

    @override
    async def _disconnect_all_coils(self) -> None:
        """Command for disconnecting all the coils."""
        await self._send_command("R")

    @override
    async def _reset_all_counters(self) -> None:
        """Command for resetting all the counters."""
        await self._send_command("C")

    @override
    async def _decrease_value_counter(self, item_id: str, value: int) -> None:
        """Command for decreasing specific counter."""
        await self._send_command("c", item_id, str(value))

    def _get_counter_mode(self, item_id: str) -> str:
        """Get the current mode of the counter."""
        result = self.counter_states.get(item_id, self.COUNTER_MODES[0])
        return str(result)

    async def _set_counter_mode(self, item_id: str, mode: str) -> None:
        """Set the new mode of the counter."""
        current_settings = await self.api_client.fetch_settings()

        root = defused_ET.fromstring(current_settings)

        item = root.find(f".//set[@box='10']/item[@id='{item_id}']")
        if item is None:
            raise DeviceParseError(
                f"Item {item_id} not found in settings in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        try:
            mode_index = self.COUNTER_MODES.index(mode)
        except ValueError as err:
            raise DeviceLogicError(
                f"Invalid counter mode: {mode}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from err

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

        response = await self.api_client.write_command(
            xml_payload, f"{self.name} ({self.location})"
        )
        self._check_response(response)

        self.counter_states[item_id] = mode

    @override
    def _parse_initial_settings(self) -> None:
        """Parse the initial settings XML to configure device properties.

        This method counts the total number of hardware inputs and outputs,
        initializes the states for all counter modes, and determines the
        global temperature unit used by the device.
        """

        if self.settings_root is None:
            return

        try:
            input_items = self.settings_root.findall(".//set[@box='10']/item")
            output_items = self.settings_root.findall(".//set[@box='11']/item")

            self.number_inputs = len(input_items)
            self.number_outputs = len(output_items)

            for item in input_items:
                if (item_id := item.get("id")) is None:
                    continue

                mode_index_str = item.get("cnt", "0")

                try:
                    mode_index = int(mode_index_str)
                    if 0 <= mode_index < len(self.COUNTER_MODES):
                        self.counter_states[item_id] = self.COUNTER_MODES[mode_index]
                except ValueError as err:
                    raise DeviceLogicError(
                        f"Invalid mode index for item {item_id}: {mode_index_str}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
                    ) from err

            box_elem = self.settings_root.find(".//set[@box='8']")
            if box_elem is not None:
                unit = box_elem.get("units")
                if unit == "C":
                    self.temperature_unit = "°C"
                elif unit == "F":
                    self.temperature_unit = "°F"
                else:
                    self.temperature_unit = "K"

        except (defused_ET.ParseError, ValueError, TypeError) as err:
            raise DeviceParseError(
                f"Failed to parse initial settings: {err}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from err

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
    async def _turn_on_coil(self, item_id: str) -> None:
        """Command for turning on the coil by its id."""
        await self._send_command("s", item_id)

    @override
    async def _turn_off_coil(self, item_id: str) -> None:
        """Command for turning off the coil by its id."""
        await self._send_command("r", item_id)

    async def _send_command(
        self,
        cmd_type: str,
        item_id: str | None = None,
        counter: str | None = None,
        time: str | None = None,
    ) -> None:
        raw_params = {
            "type": cmd_type,
            "id": item_id,
            "cnt": counter,
            "time": time,
        }
        params = {key: value for key, value in raw_params.items() if value is not None}

        response = await self.api_client.read_command(
            params, f"{self.name} ({self.location})"
        )

        self._check_response(response)

    def _check_response(self, response_text: str) -> None:
        """Checks the response of the requests."""

        root = defused_ET.fromstring(response_text)
        result_tag = find_tag(root, "result")

        if result_tag is not None:
            status = result_tag.attrib.get("status")

            if status == ERROR_STATUS:
                raise DeviceResponseError(
                    f"{self.name} ({self.location}) - {self.api_client.ip_address} returned an error, whole response: {response_text}"
                )
        else:
            raise DeviceResponseError(
                f"Response doesn't have the result tag! In the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )


class QuidoRS485(QuidoBase):
    """NotImplemented."""


async def async_setup_quido(transport: PapouchTransport) -> QuidoBase:
    """Async factory for Quido devices."""
    settings = await transport.fetch_settings()
    info = await transport.fetch_info()
    return QuidoETH(transport, settings, info)

    # if transport.protocol == "http":
    #     return QuidoETH(transport, settings, info)

    # return QuidoRS485(transport, settings, info)
