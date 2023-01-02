"""The lutron_caseta integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, TypedDict

from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant.helpers.entity import DeviceInfo


@dataclass
class LutronCasetaData:
    """Data for the lutron_caseta integration."""

    bridge: Smartbridge
    bridge_device: dict[str, Any]
    keypad_data: LutronKeypadData


@dataclass
class LutronKeypadData:
    """Data for the lutron_caseta integration keypads."""

    dr_device_id_to_keypad: dict[str, LutronKeypad]
    keypads: dict[int, LutronKeypad]
    buttons: dict[int, LutronButton]
    button_names_to_leap: dict[int, dict[str, int]]
    trigger_schemas: dict[int, vol.Schema]


class LutronKeypad(TypedDict):
    """A lutron_caseta keypad device."""

    lutron_device_id: int
    dr_device_id: str
    area_id: int
    area_name: str
    name: str
    serial: str
    device_info: DeviceInfo
    model: str
    type: str
    buttons: list[int]


LUTRON_KEYPAD_LUTRON_DEVICE_ID: Final = "lutron_device_id"
LUTRON_KEYPAD_DEVICE_REGISTRY_DEVICE_ID: Final = "dr_device_id"
LUTRON_KEYPAD_AREA_ID: Final = "area_id"
LUTRON_KEYPAD_AREA_NAME: Final = "area_name"
LUTRON_KEYPAD_NAME: Final = "name"
LUTRON_KEYPAD_SERIAL: Final = "serial"
LUTRON_KEYPAD_DEVICE_INFO: Final = "device_info"
LUTRON_KEYPAD_MODEL: Final = "model"
LUTRON_KEYPAD_TYPE: Final = "type"
LUTRON_KEYPAD_BUTTONS: Final = "buttons"


class LutronButton(TypedDict):
    """A lutron_caseta button."""

    lutron_device_id: int
    leap_button_number: int
    button_name: str
    led_device_id: str | None
    parent_keypad: int


LUTRON_BUTTON_LUTRON_DEVICE_ID: Final = "lutron_device_id"
LUTRON_BUTTON_LEAP_BUTTON_NUMBER: Final = "leap_button_number"
LUTRON_BUTTON_BUTTON_NAME: Final = "button_name"
LUTRON_BUTTON_LED_DEVICE_ID: Final = "led_device_id"
LUTRON_BUTTON_PARENT_KEYPAD: Final = "parent_keypad"
