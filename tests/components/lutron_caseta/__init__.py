"""Tests for the Lutron Caseta integration."""

from datetime import timedelta
import logging
import asyncio
from collections.abc import Callable
from typing import Any

from unittest.mock import patch

from homeassistant.components.light import ColorMode
from homeassistant.components.lutron_caseta import DOMAIN
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

ENTRY_MOCK_DATA = {
    CONF_HOST: "1.1.1.1",
    CONF_KEYFILE: "",
    CONF_CERTFILE: "",
    CONF_CA_CERTS: "",
}

_LEAP_DEVICE_TYPES = {
    "light": [
        "WallDimmer",
        "PlugInDimmer",
        "InLineDimmer",
        "SunnataDimmer",
        "TempInWallPaddleDimmer",
        "WallDimmerWithPreset",
        "Dimmed",
    ],
    "switch": [
        "WallSwitch",
        "OutdoorPlugInSwitch",
        "PlugInSwitch",
        "InLineSwitch",
        "PowPakSwitch",
        "SunnataSwitch",
        "TempInWallPaddleSwitch",
        "Switched",
    ],
    "fan": [
        "CasetaFanSpeedController",
        "MaestroFanSpeedController",
        "FanSpeed",
    ],
    "cover": [
        "SerenaHoneycombShade",
        "SerenaRollerShade",
        "TriathlonHoneycombShade",
        "TriathlonRollerShade",
        "QsWirelessShade",
        "QsWirelessHorizontalSheerBlind",
        "QsWirelessWoodBlind",
        "RightDrawDrape",
        "Shade",
        "SerenaTiltOnlyWoodBlind",
    ],
    "sensor": [
        "Pico1Button",
        "Pico2Button",
        "Pico2ButtonRaiseLower",
        "Pico3Button",
        "Pico3ButtonRaiseLower",
        "Pico4Button",
        "Pico4ButtonScene",
        "Pico4ButtonZone",
        "Pico4Button2Group",
        "FourGroupRemote",
        "SeeTouchTabletopKeypad",
        "SunnataKeypad",
        "SunnataKeypad_2Button",
        "SunnataKeypad_3ButtonRaiseLower",
        "SunnataKeypad_4Button",
        "SeeTouchHybridKeypad",
        "SeeTouchInternational",
        "SeeTouchKeypad",
        "HomeownerKeypad",
        "GrafikTHybridKeypad",
        "AlisseKeypad",
        "PalladiomKeypad",
    ],
}


class MockBridge:
    """Mock Lutron bridge that emulates configured connected status."""

    _subscribers = {}

    def __init__(self, can_connect=True, timeout_on_connect=False) -> None:
        """Initialize MockBridge instance with configured mock connectivity."""
        self.timeout_on_connect = timeout_on_connect
        self.can_connect = can_connect
        self.is_currently_connected = False
        self.areas = self.load_areas()
        self.occupancy_groups = {}
        self.scenes = self.get_scenes()
        self.devices = self.load_devices()
        self.buttons = self.load_buttons()

    async def connect(self):
        """Connect the mock bridge."""
        if self.timeout_on_connect:
            await asyncio.Event().wait()  # wait forever
        if self.can_connect:
            self.is_currently_connected = True

    def add_subscriber(self, device_id: str, callback_):
        """Mock a listener to be notified of state changes."""
        self._subscribers[device_id] = callback_

    def add_button_subscriber(self, button_id: str, callback_):
        """Mock a listener for button presses."""

    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self.is_currently_connected

    def load_areas(self):
        """Loak mock areas into self.areas."""
        return {
            "3": {"id": "3", "name": "House", "parent_id": None},
            "898": {"id": "898", "name": "Basement", "parent_id": "3"},
            "822": {"id": "822", "name": "Bedroom", "parent_id": "898"},
            "910": {"id": "910", "name": "Bathroom", "parent_id": "898"},
            "1024": {"id": "1024", "name": "Master Bedroom", "parent_id": "3"},
            "1025": {"id": "1025", "name": "Kitchen", "parent_id": "3"},
            "1026": {"id": "1026", "name": "Dining Room", "parent_id": "3"},
            "1205": {"id": "1205", "name": "Hallway", "parent_id": "3"},
        }

    async def set_value(
        self,
        device_id: str,
        value: int | None = None,
        fade_time: timedelta | None = None,
        color_value: ColorMode | None = None,
    ):
        """Mock changing device state and invoke callback."""
        self._subscribers[device_id]()

    def load_devices(self):
        """Load mock devices into self.devices."""
        return {
            "1": {
                "serial": 1234,
                "name": "bridge",
                "model": "model",
                "type": "type",
                "area": "1205",
            },
            "801": {
                "device_id": "801",
                "current_state": 100,
                "fan_speed": None,
                "zone": "801",
                "name": "Basement Bedroom_Main Lights",
                "button_groups": None,
                "type": "Dimmed",
                "model": None,
                "serial": None,
                "tilt": None,
                "area": "822",
            },
            "802": {
                "device_id": "802",
                "current_state": 100,
                "fan_speed": None,
                "zone": "802",
                "name": "Basement Bedroom_Left Shade",
                "button_groups": None,
                "type": "SerenaRollerShade",
                "model": None,
                "serial": None,
                "tilt": None,
                "area": "822",
            },
            "803": {
                "device_id": "803",
                "current_state": 100,
                "fan_speed": None,
                "zone": "803",
                "name": "Basement Bathroom_Exhaust Fan",
                "button_groups": None,
                "type": "Switched",
                "model": None,
                "serial": None,
                "tilt": None,
                "area": "910",
            },
            "804": {
                "device_id": "804",
                "current_state": 100,
                "fan_speed": None,
                "zone": "804",
                "name": "Master Bedroom_Ceiling Fan",
                "button_groups": None,
                "type": "FanSpeed",
                "model": None,
                "serial": None,
                "tilt": None,
                "area": "1024",
            },
            "901": {
                "device_id": "901",
                "current_state": 100,
                "fan_speed": None,
                "zone": "901",
                "name": "Kitchen_Main Lights",
                "button_groups": None,
                "type": "WallDimmer",
                "model": None,
                "serial": 5442321,
                "tilt": None,
                "area": "1025",
            },
            "902": {
                "device_id": "902",
                "current_state": 000,
                "fan_speed": None,
                "zone": "901",
                "name": "Kitchen_Other Lights",
                "button_groups": None,
                "type": "WallDimmer",
                "model": None,
                "serial": 5442322,
                "tilt": None,
                "area": "1025",
            },
            "9": {
                "device_id": "9",
                "current_state": -1,
                "fan_speed": None,
                "tilt": None,
                "zone": None,
                "name": "Dining Room_Pico",
                "button_groups": ["4"],
                "occupancy_sensors": None,
                "type": "Pico3ButtonRaiseLower",
                "model": "PJ2-3BRL-GXX-X01",
                "serial": 68551522,
                "device_name": "Pico",
                "area": "1026",
            },
            "1355": {
                "device_id": "1355",
                "current_state": -1,
                "fan_speed": None,
                "zone": None,
                "name": "Hallway_Main Stairs Position 1 Keypad",
                "button_groups": ["1363"],
                "type": "SunnataKeypad",
                "model": "RRST-W3RL-XX",
                "serial": 66286451,
                "control_station_name": "Main Stairs",
                "device_name": "Position 1",
                "area": "1205",
            },
        }

    def load_buttons(self):
        """Load mock buttons into self.buttons."""
        return {
            "111": {
                "device_id": "111",
                "current_state": "Release",
                "button_number": 1,
                "name": "Dining Room_Pico",
                "type": "Pico3ButtonRaiseLower",
                "model": "PJ2-3BRL-GXX-X01",
                "serial": 68551522,
                "parent_device": "9",
            },
            "1372": {
                "device_id": "1372",
                "current_state": "Release",
                "button_number": 3,
                "button_group": "1363",
                "name": "Hallway_Main Stairs Position 1 Keypad",
                "type": "SunnataKeypad",
                "model": "RRST-W3RL-XX",
                "serial": 66286451,
                "button_name": "Kitchen Pendants",
                "button_led": "1362",
                "device_name": "Kitchen Pendants",
                "parent_device": "1355",
            },
        }

    def get_devices(self) -> dict[str, dict]:
        """Will return all known devices connected to the Smart Bridge."""
        return self.devices

    def get_devices_by_domain(self, domain: str) -> list[dict]:
        """Return a list of devices for the given domain.

        :param domain: one of 'light', 'switch', 'cover', 'fan' or 'sensor'
        :returns list of zero or more of the devices
        """
        types = _LEAP_DEVICE_TYPES.get(domain)

        # return immediately if not a supported domain
        if types is None:
            return []

        return self.get_devices_by_types(types)

    def get_devices_by_type(self, type_: str) -> list[dict]:
        """Will return all devices of a given device type.

        :param type_: LEAP device type, e.g. WallSwitch
        """
        return [device for device in self.devices.values() if device["type"] == type_]

    def get_devices_by_types(self, types: list[str]) -> list[dict]:
        """Will return all devices for a list of given device types.

        :param types: list of LEAP device types such as WallSwitch, WallDimmer
        """
        return [device for device in self.devices.values() if device["type"] in types]

    def get_scenes(self):
        """Return scenes on the bridge."""
        return {}

    def get_buttons(self):
        """Will return all known buttons connected to the bridge/processor."""
        return self.buttons

    def tap_button(self, button_id: str):
        """Mock a button press and release message for the given button ID."""

    async def close(self):
        """Close the mock bridge connection."""
        self.is_currently_connected = False


def make_mock_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, data=ENTRY_MOCK_DATA)


async def async_setup_integration(
    hass: HomeAssistant,
    mock_bridge: MockBridge,
    config_entry_id: str | None = None,
    can_connect: bool = True,
    timeout_during_connect: bool = False,
    timeout_during_configure: bool = False,
) -> MockConfigEntry:
    """Set up a mock bridge."""
    if config_entry_id is None:
        mock_entry = make_mock_entry()
        mock_entry.add_to_hass(hass)
        config_entry_id = mock_entry.entry_id
    else:
        mock_entry = hass.config_entries.async_get_entry(config_entry_id)

    def create_tls_factory(
        *args: Any, on_connect_callback: Callable[[], None], **kwargs: Any
    ) -> None:
        """Return a mock bridge."""
        if not timeout_during_connect:
            on_connect_callback()
        return mock_bridge(
            can_connect=can_connect, timeout_on_connect=timeout_during_configure
        )

    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls",
        create_tls_factory,
    ):
        await hass.config_entries.async_setup(config_entry_id)
        await hass.async_block_till_done()
    return mock_entry
