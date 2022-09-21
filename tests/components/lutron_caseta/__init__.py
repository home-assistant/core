"""Tests for the Lutron Caseta integration."""


from unittest.mock import patch

from homeassistant.components.lutron_caseta import DOMAIN
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
)
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

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


async def async_setup_integration(hass, mock_bridge) -> MockConfigEntry:
    """Set up a mock bridge."""
    mock_entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_MOCK_DATA)
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls"
    ) as create_tls:
        create_tls.return_value = mock_bridge(can_connect=True)
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
    return mock_entry


class MockBridge:
    """Mock Lutron bridge that emulates configured connected status."""

    def __init__(self, can_connect=True):
        """Initialize MockBridge instance with configured mock connectivity."""
        self.can_connect = can_connect
        self.is_currently_connected = False
        self.buttons = {}
        self.areas = {}
        self.occupancy_groups = {}
        self.scenes = self.get_scenes()
        self.devices = self.load_devices()

    async def connect(self):
        """Connect the mock bridge."""
        if self.can_connect:
            self.is_currently_connected = True

    def add_subscriber(self, device_id: str, callback_):
        """Mock a listener to be notified of state changes."""

    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self.is_currently_connected

    def load_devices(self):
        """Load mock devices into self.devices."""
        return {
            "1": {"serial": 1234, "name": "bridge", "model": "model", "type": "type"},
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
            },
        }

    def get_devices(self) -> dict[str, dict]:
        """Will return all known devices connected to the Smart Bridge."""
        return self.devices

    def get_devices_by_domain(self, domain: str) -> list[dict]:
        """
        Return a list of devices for the given domain.

        :param domain: one of 'light', 'switch', 'cover', 'fan' or 'sensor'
        :returns list of zero or more of the devices
        """
        types = _LEAP_DEVICE_TYPES.get(domain, None)

        # return immediately if not a supported domain
        if types is None:
            return []

        return self.get_devices_by_types(types)

    def get_devices_by_type(self, type_: str) -> list[dict]:
        """
        Will return all devices of a given device type.

        :param type_: LEAP device type, e.g. WallSwitch
        """
        return [device for device in self.devices.values() if device["type"] == type_]

    def get_devices_by_types(self, types: list[str]) -> list[dict]:
        """
        Will return all devices for a list of given device types.

        :param types: list of LEAP device types such as WallSwitch, WallDimmer
        """
        return [device for device in self.devices.values() if device["type"] in types]

    def get_scenes(self):
        """Return scenes on the bridge."""
        return {}

    async def close(self):
        """Close the mock bridge connection."""
        self.is_currently_connected = False
