"""The lutron_caseta integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylutron_caseta.smartbridge import Smartbridge
import voluptuous as vol


@dataclass
class LutronCasetaData:
    """Data for the lutron_caseta integration."""

    bridge: Smartbridge
    bridge_device: dict[str, Any]
    dr_id_to_keypad_map: dict[str, dict]
    keypads: dict[int, Any]
    keypad_buttons: dict[int, Any]
    keypad_button_maps: dict[int, dict[str, int]]
    keypad_trigger_schemas: dict[int, vol.Schema]
