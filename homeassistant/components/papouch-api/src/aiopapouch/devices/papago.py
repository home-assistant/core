"""This file contains definition of the TH2E device."""

import logging
from typing import Any, cast, override

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient, PapouchTransport
from ..exceptions import DeviceLogicError, DeviceParseError, DeviceResponseError
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)


class PapagoETH(PapouchDevice):
    """Represents Papago device family.

    Note that it uses unified code that
    will be applicable to all of Papago devices.

    In case if there will be a new Papago
    that uses a different XML this will be wrong
    and the best option will be to create X classes
    for every concrete device. YAGNI.
    """

    api_client: PapouchHTTPClient

    SENSOR_TYPES = [
        "Unused",
        "Temperature / Humidity (TH15)",
        "Temperature (DS)",
        "Temperature / Humidity (TH3x)",
        "Temperature (TMP)",
    ]

    BOX_SENSOR_BASE = 30
    SAVE_ENDPOINT = "savesettings.xml"

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
        """Constructor for Papago device.

        Note that every Papago has a different settings XML
        so unlike other devices we don't need it here.
        """

        self.api_client = cast(PapouchHTTPClient, api_client)

        self.info_root = defused_ET.fromstring(info)
        self.settings_root = defused_ET.fromstring(settings)

        self._name = self.get_name()
        self._location = self.get_location()
        self._mac_address = self.get_mac_address()

        self.units_sensors: dict[str, dict[str, Any]] = {}
        self.type_sensors: dict[str, str] = {}

        self._parse_initial_settings()

    @override
    def parse_fresh_data(self, xml_data: str) -> dict:
        root = defused_ET.fromstring(xml_data)
        parsed_data: dict[str, dict[str, Any]] = {"sensor": {}}

        for element in root.iter():
            if not element.tag.endswith("sns"):
                continue

            base_item_id = element.attrib.get("id")
            base_name = element.attrib.get("name", "Unknown")

            if not base_item_id:
                continue

            if base_item_id not in self.units_sensors:
                self.units_sensors[base_item_id] = {
                    "name": base_name,
                    "sub_sensors": dict[str, str](),
                }

            idx = 1
            while True:
                suffix = "" if idx == 1 else str(idx)
                sns_type = element.attrib.get(f"type{suffix}")

                if sns_type is None:
                    break

                item_id = base_item_id if idx == 1 else f"{base_item_id}_{idx}"
                unit_code = element.attrib.get(f"unit{suffix}", "0")
                status = element.attrib.get(f"status{suffix}", "0")

                self.units_sensors[base_item_id]["sub_sensors"][item_id] = {
                    "type": sns_type,
                    "unit": unit_code,
                }

                if status in ("1", "4"):
                    parsed_data["sensor"][item_id] = None
                else:
                    parsed_data["sensor"][item_id] = float(
                        element.attrib.get(f"val{suffix}", "0")
                    )

                idx += 1

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
        buttons = []

        for base_id, sensor_data in self.units_sensors.items():
            sensor_name = sensor_data.get("name", f"Sensor {base_id}")
            buttons.append(
                {
                    "name": f"Set {sensor_name} automatically",
                    "cmd": f"set_sensor_{base_id}",
                }
            )

        return buttons

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

        for sensor_data in self.units_sensors.values():
            sensor_name = sensor_data["name"]

            for sub_id, sub_data in sensor_data["sub_sensors"].items():
                sns_type = sub_data["type"]
                unit_code = sub_data["unit"]

                if sns_type == "1":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Temperature",
                            "device_class": "temperature",
                            "unit": unit_map.get(unit_code, "°C"),
                        }
                    )
                elif sns_type == "2":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Humidity",
                            "device_class": "humidity",
                            "unit": "%",
                        }
                    )
                elif sns_type == "3":
                    sensors.append(
                        {
                            "item_id": sub_id,
                            "type": "sensor",
                            "name": f"{sensor_name} Dew Point",
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
        selects = []

        for base_id, sensor_data in self.units_sensors.items():
            sensor_name = sensor_data.get("name", f"Sensor {base_id}")
            selects.append(
                {
                    "item_id": base_id,
                    "category": "sensor_type",
                    "name": f"{sensor_name} type",
                    "options": self.SENSOR_TYPES,
                }
            )

        return selects

    @override
    async def execute_button_command(self, cmd_type: str) -> None:
        if "set_sensor" not in cmd_type:
            raise DeviceLogicError(
                f"Unsupported command: {cmd_type}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        sensor_id = cmd_type.split("_")[2]
        await self._auto_detect_sensor(sensor_id)

    async def _auto_detect_sensor(self, sensor_id: str) -> None:
        """Send command to automatically detect the connected sensor."""
        result_id = str(int(sensor_id) + 3)
        payload = f'<root><set box="98" num01="{result_id}" /></root>'

        response = await self.api_client.write_command(
            payload, f"{self.name} ({self.location})", self.SAVE_ENDPOINT
        )

        if not response:
            return

        root = defused_ET.fromstring(response)

        result_tag = find_tag(root, "result")
        if result_tag is not None and result_tag.attrib.get("status") not in ("1", "4"):
            raise DeviceResponseError(
                f"{self.name} ({self.location}) - {self.api_client.ip_address} returned an error while auto-detecting sensor, whole response: {response}"
            )

        for element in root.iter("set"):
            box_id = element.attrib.get("box")
            sns_type = element.attrib.get("type")

            if box_id and box_id.isdigit() and sns_type is not None:
                box_num = int(box_id)
                if self.BOX_SENSOR_BASE <= box_num <= self.BOX_SENSOR_BASE + 1:
                    s_id = str(box_num - self.BOX_SENSOR_BASE + 1)
                    self.type_sensors[s_id] = sns_type

    async def _set_sensor_type(self, item_id: str, type_idx: str) -> None:
        settings = await self.api_client.fetch_settings()

        try:
            settings_root = defused_ET.fromstring(settings)
        except defused_ET.ParseError as exception:
            raise DeviceParseError(
                f"Invalid settings XML: {exception}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from exception

        def format_val(val: str) -> str:
            return val.removesuffix(".0")

        box_num = int(item_id) - 1 + self.BOX_SENSOR_BASE
        target_box = None

        for element in settings_root.iter("set"):
            if element.attrib.get("box") == str(box_num):
                target_box = element
                break

        if target_box is None:
            raise DeviceParseError(
                f"Box {box_num} not found in settings, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        ordered_keys = [
            ("num01", "type"),
            ("num02", "watch"),
            ("num03", "watch2"),
            ("num04", "watch3"),
            ("str00", "name"),
            ("str01", "min"),
            ("str02", "max"),
            ("str03", "hyst"),
            ("str04", "min2"),
            ("str05", "max2"),
            ("str06", "hyst2"),
            ("str07", "min3"),
            ("str08", "max3"),
            ("str09", "hyst3"),
        ]

        safe_defaults = {
            "name": f"Sensor {item_id}",
            "watch": "0",
            "watch2": "0",
            "watch3": "0",
            "min": "-40",
            "max": "125",
            "hyst": "0",
            "min2": "0",
            "max2": "100",
            "hyst2": "0",
            "min3": "-40",
            "max3": "125",
            "hyst3": "0",
        }

        payload_parts = [f'<set box="{box_num}"']

        for post_key, read_key in ordered_keys:
            if read_key == "type":
                val = str(type_idx)
            else:
                raw_val = target_box.attrib.get(
                    read_key, safe_defaults.get(read_key, "0")
                )
                val = format_val(raw_val)

            payload_parts.append(f'{post_key}="{val}"')

        payload_parts.append("/>")

        xml_payload = f'<?xml version="1.0" encoding="iso-8859-2"?>\n<root>{" ".join(payload_parts)}</root>'

        resp_start = await self.api_client.write_command(
            '<root><set box="0" /></root>',
            f"{self.name} ({self.location})",
            self.SAVE_ENDPOINT,
        )

        self._check_sensor_response(
            resp_start,
            expected_status="1",
            action_msg="opening configuration transaction",
        )

        resp_data = await self.api_client.write_command(
            xml_payload, f"{self.name} ({self.location})", self.SAVE_ENDPOINT
        )
        self._check_sensor_response(
            resp_data, expected_status="1", action_msg="setting the type of the sensor"
        )

        resp_save = await self.api_client.write_command(
            '<root><set box="99" /></root>',
            f"{self.name} ({self.location})",
            self.SAVE_ENDPOINT,
        )
        self._check_sensor_response(
            resp_save,
            expected_status="2",
            action_msg="saving and restarting the device",
        )

        self.type_sensors[item_id] = str(type_idx)

    def _check_sensor_response(
        self, response_text: str, expected_status: str, action_msg: str
    ) -> None:
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

        except defused_ET.ParseError as exception:
            raise DeviceParseError(
                f"Invalid XML response from device: {exception}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from exception

    @override
    async def turn_on_switch(self, item_id: str) -> None:
        """Unused in Papago."""
        return

    @override
    async def turn_off_switch(self, item_id: str) -> None:
        """Unused in Papago."""
        return

    @override
    async def set_number_value(self, category: str, item_id: str, value: float) -> None:
        """Unused in Papago."""
        return

    @override
    def get_select_option(self, category: str, item_id: str) -> str | None:
        if category == "sensor_type":
            sns_type = self.type_sensors.get(item_id)
            if sns_type is not None and sns_type.isdigit():
                type_idx = int(sns_type)
                if 0 <= type_idx < len(self.SENSOR_TYPES):
                    return self.SENSOR_TYPES[type_idx]

        return None

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        if category == "sensor_type":
            try:
                type_idx = str(self.SENSOR_TYPES.index(option))
            except ValueError:
                return

            await self._set_sensor_type(item_id, type_idx)

    @override
    async def switch_to_web_mode(self) -> None:
        """Unused in Papago."""

    @override
    def _parse_initial_settings(self) -> None:
        """For now it sets types of the sensors."""
        for element in self.settings_root.iter():
            if element.tag != "set":
                continue

            box_id = element.attrib.get("box")
            if not box_id or not box_id.isdigit():
                continue

            box_num = int(box_id)

            if self.BOX_SENSOR_BASE <= box_num <= self.BOX_SENSOR_BASE + 1:
                sns_type = element.attrib.get("type")

                if sns_type is not None:
                    sensor_id = str(box_num - self.BOX_SENSOR_BASE + 1)
                    self.type_sensors[sensor_id] = str(sns_type)


async def async_setup_papago(transport: PapouchTransport) -> PapagoETH:
    """Async factory for Papago devices."""
    settings = await transport.fetch_settings()
    info = await transport.fetch_info()

    return PapagoETH(transport, settings, info)

    # if transport.protocol == "http":
    #     return PapagoETH(transport, settings, info)

    # return PapagoRS485(transport, settings, info)
