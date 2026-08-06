"""This file contains classes that define Papouch devices."""

from abc import ABC, abstractmethod
import logging
from typing import Any, cast, override
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient, PapouchTransport
from ..exceptions import DeviceParseError, DeviceResponseError
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)
TEMP_MULTIPLICATIVE_CONST = 10


class TMEBase(PapouchDevice, ABC):
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

    def __init__(self, api_client: PapouchTransport, info: str, settings: str) -> None:
        """Constructor for TME device."""

        self.api_client = cast(PapouchHTTPClient, api_client)

        self.info_root = defused_ET.fromstring(info)

        # We need settings only for MAC address so None value is solved there
        if settings:
            self.settings_root = defused_ET.fromstring(settings)
        else:
            self.settings_root = None

        self._name = self.get_name()
        self._location = self.get_location()
        self._mac_address = self.get_mac_address()

        self.sensors: dict[str, dict[str, Any]] = {}

        self._parse_initial_settings()

    @override
    async def parse_fresh_data(self, xml_data: str) -> dict:
        """Parse fresh data. Extracts global unit and delegates to specific parsers."""
        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {"sensor": {}}

        status_tag = find_tag(root, "status")
        global_unit = (
            status_tag.attrib.get("unit", "C") if status_tag is not None else "C"
        )

        for element in root.iter():
            if element.tag == "sns":
                await self._parse_sns_element(element, parsed_data, global_unit)

        return parsed_data

    @abstractmethod
    async def _parse_sns_element(
        self,
        element: defused_ET.Element,
        parsed_data: dict[str, dict[str, Any]],
        global_unit: str,
    ) -> None:
        """Must be implemented by subclasses to handle specific XML structure."""

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

        if self.settings_root is not None:
            box_12 = self.settings_root.find(".//set[@box='12']")
            if box_12 is not None and "mac" in box_12.attrib:
                return str(box_12.attrib["mac"])

        raise DeviceParseError(
            f"The device doesn't have a MAC address in settings.xml nor fresh.xml, "
            f"device: {self.name} ({self.location}) - {self.api_client.ip_address}"
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
        """Unified method for returning sensors for Home Assistant."""
        sensors = []

        for sensor_data in self.sensors.values():
            sensor_name = sensor_data.get("name", "Sensor")

            for sub_id, sub_data in sensor_data.get("sub_sensors", {}).items():
                sns_type = sub_data["type"]
                unit = sub_data["unit"]

                if sns_type == "1":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Temperature".strip(),
                            "device_class": "temperature",
                            "state_class": "measurement",
                            "unit": unit,
                        }
                    )
                elif sns_type == "2":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Humidity".strip(),
                            "device_class": "humidity",
                            "state_class": "measurement",
                            "unit": unit,
                        }
                    )
                elif sns_type == "batt":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Battery".strip(),
                            "device_class": "battery",
                            "state_class": "measurement",
                            "unit": "%",
                        }
                    )
                elif sns_type == "rssi":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Signal Strength".strip(),
                            "device_class": "signal_strength",
                            "state_class": "measurement",
                            "unit": "dBm",
                        }
                    )

        return sensors

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
    def _parse_initial_settings(self) -> None:
        pass


class TME(TMEBase):
    """Defines classic TME device with single sensor."""

    ITEM_ID = "1"

    @override
    async def _parse_sns_element(
        self,
        element: defused_ET.Element,
        parsed_data: dict[str, dict[str, Any]],
        global_unit: str,
    ) -> None:
        """Parse classic TME XML format."""
        if self.ITEM_ID not in self.sensors:
            self.sensors[self.ITEM_ID] = {"name": "TME", "sub_sensors": {}}

        status = element.attrib.get("status", "0")
        unit_code = element.attrib.get("unit", "0")
        real_unit = self._get_unit(self.TEMPERATURE_SNS_TYPE, unit_code)

        self.sensors[self.ITEM_ID]["sub_sensors"][self.ITEM_ID] = {
            "type": "1",
            "unit": real_unit,
        }

        if status in ("1", "4"):
            parsed_data["sensor"][self.ITEM_ID] = None
        else:
            value = element.attrib.get("val", "0")
            try:
                parsed_data["sensor"][self.ITEM_ID] = float(value) / 10.0
            except ValueError as err:
                raise DeviceParseError(
                    f"{self.name} ({self.location}) - {self.api_client.ip_address} returned an error while parsing value: '{value}' from sensor"
                ) from err

    @override
    async def switch_to_web_mode(self) -> None:
        """Unused in TME."""


class TMERadioMulti(TMEBase):
    """Defines THE Multi / Radio device."""

    @override
    async def _parse_sns_element(
        self,
        element: defused_ET.Element,
        parsed_data: dict[str, dict[str, Any]],
        global_unit: str,
    ) -> None:
        """Parse Multi/Radio format."""

        formatted_temp_unit = (
            f"°{global_unit}" if global_unit in ("C", "F") else global_unit
        )

        base_item_id = element.attrib.get("id", "1")
        base_name = element.attrib.get("name", "Sensor")

        if base_item_id not in self.sensors:
            self.sensors[base_item_id] = {
                "name": base_name,
                "sub_sensors": {},
            }

        idx = 1
        while True:
            status_str = element.attrib.get(f"s{idx}")
            raw_val = element.attrib.get(f"v{idx}")

            if status_str is None or raw_val is None:
                break

            item_id = base_item_id if idx == 1 else f"{base_item_id}_{idx}"

            final_unit = formatted_temp_unit if idx == 1 else "%"

            self.sensors[base_item_id]["sub_sensors"][item_id] = {
                "type": str(idx),
                "unit": final_unit,
            }

            if status_str != "0":
                parsed_data["sensor"][item_id] = None
            else:
                try:
                    parsed_data["sensor"][item_id] = float(raw_val) / 10.0
                except ValueError:
                    parsed_data["sensor"][item_id] = None

            idx += 1

        batt = element.attrib.get("batt")
        if batt is not None:
            batt_value = round((int(batt) - 1) * (100 / 7), 1)
            batt_id = f"{base_item_id}_batt"
            self.sensors[base_item_id]["sub_sensors"][batt_id] = {
                "type": "batt",
                "unit": "%",
            }
            parsed_data["sensor"][batt_id] = batt_value

        rssi = element.attrib.get("rssi")
        if rssi is not None:
            rssi_id = f"{base_item_id}_rssi"
            self.sensors[base_item_id]["sub_sensors"][rssi_id] = {
                "type": "rssi",
                "unit": "dBm",
            }
            parsed_data["sensor"][rssi_id] = int(rssi)

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


async def async_setup_tme(transport: PapouchTransport) -> TMEBase | None:
    """Async factory for TME device."""
    info = await transport.fetch_info()
    settings = await transport.fetch_settings()

    # if transport.protocol == "http":

    root_info = defused_ET.fromstring(info)
    heartbeat_tag = find_tag(root_info, "heartbeat")

    if heartbeat_tag is None:
        raise DeviceParseError("This TME doesn't have heartbeat tag.")

    device_name = heartbeat_tag.attrib.get("device")

    if device_name == "TME":
        return TME(transport, info, settings)
    if device_name in {"TME radio", "TME MULTI"}:
        return TMERadioMulti(transport, info, settings)

    _LOGGER.error("Unsupported TME: %s", device_name)
    return None
