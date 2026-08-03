"""This file contains definition of the Papago device family."""

from dataclasses import dataclass
import logging
from typing import Any, cast, override

import defusedxml.ElementTree as defused_ET

from ..client import PapouchHTTPClient, PapouchTransport
from ..exceptions import DeviceLogicError, DeviceParseError, DeviceResponseError
from .base import PapouchDevice, find_tag

_LOGGER = logging.getLogger(__name__)


@dataclass
class InputSettings:
    """Contains information about 1 input of Papago."""

    name: str
    unit: str
    decimal_count: str
    trigger_impulse_count: str  # how much impulses are needed to increase counter
    value_to_add: str  # and by how many
    type_cnt: str
    box_num: int


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

    COUNTER_MODES = [
        "Counter off",
        "Count falling edges",
        "Count rising edges",
        "Count all edges",
    ]

    BOX_SENSOR_BASE = 30

    SAVE_ENDPOINT = "savesettings.xml"

    SENSOR_SETTINGS_KEYS = [
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

    INPUT_ID_INCREMENT = 1000

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

    def __init__(
        self,
        api_client: PapouchTransport,
        settings: str,
        device_name: str,
        location: str,
    ) -> None:
        """Constructor for Papago device."""

        self.api_client = cast(PapouchHTTPClient, api_client)

        self.settings_root = defused_ET.fromstring(settings)

        self._name = device_name
        self._location = location
        self._mac_address = self.get_mac_address()

        # Base class contains nested sensor and their types
        # although not every Papago device even has more than 1 sensor

        self.units_sensors: dict[str, dict[str, Any]] = {}
        self.type_sensors: dict[str, str] = {}

        self.number_outputs = 0

        self.inputs: dict[str, InputSettings] = {}

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
        raise DeviceLogicError("Papago shouldn't use this method!")

    @override
    def get_name(self) -> str:
        raise DeviceLogicError("Papago shouldn't use this method!")

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
        """Unused in Papago."""
        return []

    @override
    def get_supported_numbers(self) -> list[dict[str, Any]]:
        """Unused in Papago."""
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
        """Unused in Papago."""
        return []

    @override
    def get_supported_selects(self) -> list[dict[str, Any]]:
        selects = []

        for item_id, sensor_data in self.units_sensors.items():
            sensor_name = sensor_data.get("name", f"Sensor {item_id}")
            selects.append(
                {
                    "item_id": item_id,
                    "category": "sensor_type",
                    "name": f"{sensor_name} type",
                    "options": self.SENSOR_TYPES,
                }
            )

        for item_id, input_data in self.inputs.items():
            selects.append(
                {
                    "item_id": str(int(item_id) + self.INPUT_ID_INCREMENT),
                    "category": "input_type",
                    "name": f"{input_data.name} counter mode",
                    "options": self.COUNTER_MODES,
                }
            )

        return selects

    async def _update_settings(self) -> None:
        settings = await self.api_client.fetch_settings()

        try:
            self.settings_root = defused_ET.fromstring(settings)
        except defused_ET.ParseError as exception:
            raise DeviceParseError(
                f"Invalid settings XML: {exception}, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from exception

        self._parse_initial_settings()

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

        await self._check_auto_detect_sensor_response(response)

    async def _check_auto_detect_sensor_response(self, response: str) -> None:
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
        await self._update_settings()

        def format_val(val: str) -> str:
            return val.removesuffix(".0")

        box_num = int(item_id) - 1 + self.BOX_SENSOR_BASE
        target_box = None

        for element in self.settings_root.iter("set"):
            if element.attrib.get("box") == str(box_num):
                target_box = element
                break

        if target_box is None:
            raise DeviceParseError(
                f"Box {box_num} not found in settings, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        safe_defaults = {
            "name": f"Sensor {item_id}",
            "tunit": "0",
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

        for post_key, read_key in self.SENSOR_SETTINGS_KEYS:
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

        self._save_setting(xml_payload)

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

    async def _save_setting(self, xml_payload: str) -> None:
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

    async def _set_input_type(self, item_id: str, type_idx: str) -> None:
        """Set the counter mode for a specific input."""

        await self._update_settings()

        try:
            real_input_id = str(int(item_id) - self.INPUT_ID_INCREMENT)
        except ValueError as err:
            raise DeviceLogicError(
                f"Invalid item_id format for input: {item_id}"
                f"device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            ) from err

        input_item = self.inputs.get(real_input_id)
        if not input_item:
            raise DeviceLogicError(
                f"Input with ID {real_input_id} not found in parsed data, "
                f"device: {self.name} ({self.location}) - {self.api_client.ip_address}"
            )

        box_num = input_item.box_num

        if type_idx == "0":
            payload_content = (
                f'<set box="{box_num}" num01="0" str01="{input_item.name}" />'
            )
        else:
            payload_content = (
                f'<set box="{box_num}" '
                f'num01="{type_idx}" '
                f'num02="{input_item.decimal_count}" '
                f'str01="{input_item.name}" '
                f'str02="{input_item.trigger_impulse_count}" '
                f'str03="{input_item.value_to_add}" '
                f'str04="{input_item.unit}" />'
            )

        xml_payload = f'<?xml version="1.0" encoding="iso-8859-2"?>\n<root>{payload_content}</root>'

        await self._save_setting(xml_payload)

        input_item.type_cnt = type_idx

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

        if category == "input_type":
            real_input_id = str(int(item_id) - self.INPUT_ID_INCREMENT)
            input_item = self.inputs.get(real_input_id)
            if input_item and str(input_item.type_cnt).isdigit():
                mode_idx = int(input_item.type_cnt)
                if 0 <= mode_idx < len(self.COUNTER_MODES):
                    return self.COUNTER_MODES[mode_idx]

        return None

    @override
    async def set_select_option(self, category: str, item_id: str, option: str) -> None:
        if category == "sensor_type":
            try:
                type_idx = str(self.SENSOR_TYPES.index(option))
            except ValueError:
                return

            await self._set_sensor_type(item_id, type_idx)

        if category == "input_type":
            try:
                type_idx = str(self.COUNTER_MODES.index(option))
            except ValueError:
                return

            await self._set_input_type(item_id, type_idx)

    @override
    async def switch_to_web_mode(self) -> None:
        """Unused in Papago."""
        raise DeviceLogicError("Calling not implemented method.")

    @override
    def _parse_initial_settings(self) -> None:
        """Base method for other devices to parse their settings."""
        raise DeviceLogicError("Calling not implemented method.")


class PapagoETH_2TH(PapagoETH):
    """Represents Papago 2TH ETH."""

    @override
    def _parse_initial_settings(self) -> None:
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


class PapagoETH_1TH_2DI_1DO(PapagoETH):
    """Represents Papago 1TH 2DI 1DO ETH."""

    BOX_SENSOR_BASE = 40

    # note that there will be always 1 output
    BOX_OUTPUT_BASE = 30

    BOX_INPUT_BASE = 31

    SENSOR_SETTINGS_KEYS = [
        ("num00", "tunit"),
        ("num01", "type"),
        ("num02", "watch"),
        ("num03", "watch2"),
        ("num04", "watch3"),
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

    @override
    def _parse_initial_settings(self) -> None:
        """Note that this Papago has only 1 sensor, but we still use the list from parent class."""

        for element in self.settings_root.iter():
            if element.tag != "set":
                continue

            box_id = element.attrib.get("box")
            if not box_id or not box_id.isdigit():
                continue

            box_num = int(box_id)

            match box_num:
                case self.BOX_SENSOR_BASE:
                    sns_type = element.attrib.get("type")

                    if sns_type is None:
                        raise DeviceParseError(
                            f"The is no sensor type during parsing initial settings, in the device: {self.name} ({self.location}) - {self.api_client.ip_address}"
                        )

                    self.type_sensors["1"] = str(sns_type)

                    self.units_sensors["1"] = {
                        "name": "Sensor",
                        "sub_sensors": {
                            "1": {
                                "type": str(sns_type),
                                "unit": "0",
                            }
                        },
                    }

                case self.BOX_OUTPUT_BASE:
                    # TODO
                    continue

                case x if self.BOX_INPUT_BASE <= x < self.BOX_SENSOR_BASE:
                    counter_id = str(box_num - self.BOX_INPUT_BASE + 1)

                    name = element.attrib.get("name", f"Input {counter_id}")
                    unit = element.attrib.get("unit", "")
                    dec = element.attrib.get("dec", "0")
                    trigger_impulse_count = element.attrib.get("src", "1")
                    value_to_add = element.attrib.get("dst", "1")
                    type_cnt = element.attrib.get("enb", "0")

                    self.inputs[counter_id] = InputSettings(
                        name,
                        unit,
                        dec,
                        trigger_impulse_count,
                        value_to_add,
                        type_cnt,
                        box_num,
                    )

                case _:
                    continue


async def async_setup_papago(transport: PapouchTransport) -> PapagoETH:
    """Async factory for Papago devices."""
    settings = await transport.fetch_settings()
    info = await transport.fetch_info()

    # if transport.protocol == "http":

    root_info = defused_ET.fromstring(info)
    heartbeat_tag = find_tag(root_info, "heartbeat")
    device_name = heartbeat_tag.attrib.get("device")
    location = heartbeat_tag.attrib.get("location")

    if device_name == "Papago 2TH ETH":
        return PapagoETH_2TH(transport, settings, device_name, location)
    if device_name == "Papago 1TH 2DI 1DO ETH":
        return PapagoETH_1TH_2DI_1DO(transport, settings, device_name, location)

    raise DeviceLogicError(f"Unsupported Papago: {device_name}, location: {location}")
