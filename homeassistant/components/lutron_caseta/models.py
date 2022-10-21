"""The lutron_caseta integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol

from homeassistant.helpers.entity import DeviceInfo


@dataclass
class LutronCasetaData:
    """Data for the lutron_caseta integration."""

    bridge: Smartbridge
    bridge_device: dict[str, Any]
    button_devices: dict[str, dict]
    device_info_by_device_id: dict[int, DeviceInfo]
    keypad_button_types_to_leap_by_keypad_id: dict[str, dict[str, int]]
    keypad_button_trigger_schema_by_keypad_id: dict[str, vol.Schema]
