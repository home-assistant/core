"""Fixtures for OpenRGB integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openrgb.utils import DeviceType, ModeFlags, RGBColor
import pytest

from homeassistant.components.openrgb.const import DOMAIN, OpenRGBMode
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Computer",
        data={
            CONF_NAME: "Test Computer",
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6742,
        },
        entry_id="01J0EXAMPLE0CONFIGENTRY00",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.openrgb.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_device_data() -> dict[str, Any]:
    """Return mock device data for creating OpenRGB devices.

    Based on real ENE DRAM device data from OpenRGB server.
    """
    return {
        "name": "Test RGB Device",
        "type": DeviceType.LEDSTRIP,
        "metadata": {
            "vendor": "Test Vendor",
            "description": "Test LED Strip",
            "version": "1.0.0",
            "serial": "TEST123",
            "location": "Test Location",
        },
        "active_mode": 0,  # Direct mode
        "modes": [
            {
                "name": OpenRGBMode.DIRECT,
                "value": 65535,
                "flags": ModeFlags.HAS_PER_LED_COLOR,
                "speed_min": None,
                "speed_max": None,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": None,
                "brightness": None,
                "direction": None,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": OpenRGBMode.OFF,
                "value": 0,
                "flags": 0,
                "speed_min": None,
                "speed_max": None,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": None,
                "brightness": None,
                "direction": None,
                "color_mode": 0,
                "colors": [],
            },
            {
                "name": OpenRGBMode.STATIC,
                "value": 1,
                "flags": ModeFlags.HAS_PER_LED_COLOR,
                "speed_min": None,
                "speed_max": None,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": None,
                "brightness": None,
                "direction": None,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Breathing",
                "value": 2,
                "flags": ModeFlags.HAS_SPEED
                | ModeFlags.HAS_PER_LED_COLOR
                | ModeFlags.HAS_MODE_SPECIFIC_COLOR,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 2,
                "brightness": None,
                "direction": None,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Flashing",
                "value": 3,
                "flags": ModeFlags.HAS_SPEED | ModeFlags.HAS_MODE_SPECIFIC_COLOR,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 2,
                "brightness": None,
                "direction": None,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Spectrum Cycle",
                "value": 4,
                "flags": ModeFlags.HAS_SPEED,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 2,
                "brightness": None,
                "direction": None,
                "color_mode": 0,
                "colors": [],
            },
            {
                "name": "Rainbow",
                "value": 5,
                "flags": ModeFlags.HAS_SPEED | ModeFlags.HAS_DIRECTION_LR,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 0,
                "brightness": None,
                "direction": 0,
                "color_mode": 0,
                "colors": [],
            },
            {
                "name": "Chase Fade",
                "value": 7,
                "flags": ModeFlags.HAS_SPEED
                | ModeFlags.HAS_DIRECTION_LR
                | ModeFlags.HAS_PER_LED_COLOR
                | ModeFlags.HAS_MODE_SPECIFIC_COLOR,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 2,
                "brightness": None,
                "direction": 0,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Chase",
                "value": 9,
                "flags": ModeFlags.HAS_SPEED
                | ModeFlags.HAS_DIRECTION_LR
                | ModeFlags.HAS_PER_LED_COLOR
                | ModeFlags.HAS_MODE_SPECIFIC_COLOR,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 2,
                "brightness": None,
                "direction": 0,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Random Flicker",
                "value": 13,
                "flags": ModeFlags.HAS_SPEED,
                "speed_min": 4,
                "speed_max": 0,
                "brightness_min": None,
                "brightness_max": None,
                "colors_min": None,
                "colors_max": None,
                "speed": 2,
                "brightness": None,
                "direction": None,
                "color_mode": 0,
                "colors": [],
            },
        ],
        "zones": [{"name": "DRAM", "type": "LINEAR"}],
        "leds": [
            {"name": "Test LED 1", "id": 0},
            {"name": "Test LED 2", "id": 1},
        ],
        "colors": [
            (255, 0, 0),  # Red
            (255, 0, 0),
        ],
    }


@pytest.fixture
def mock_openrgb_device(mock_device_data: dict[str, Any]) -> MagicMock:
    """Return a mocked OpenRGB device."""
    device = MagicMock()
    device.id = 0
    device.name = mock_device_data["name"]
    device.type = MagicMock()
    device.type.name = mock_device_data["type"].name
    device.type.value = mock_device_data["type"].value

    # Metadata
    device.metadata = MagicMock()
    device.metadata.vendor = mock_device_data["metadata"]["vendor"]
    device.metadata.description = mock_device_data["metadata"]["description"]
    device.metadata.version = mock_device_data["metadata"]["version"]
    device.metadata.serial = mock_device_data["metadata"]["serial"]
    device.metadata.location = mock_device_data["metadata"]["location"]

    # Modes
    device.active_mode = mock_device_data["active_mode"]
    modes = []
    for mode_data in mock_device_data["modes"]:
        mode = MagicMock()
        mode.name = mode_data["name"]
        mode.value = mode_data["value"]
        mode.flags = mode_data["flags"]
        mode.speed_min = mode_data["speed_min"]
        mode.speed_max = mode_data["speed_max"]
        mode.brightness_min = mode_data["brightness_min"]
        mode.brightness_max = mode_data["brightness_max"]
        mode.colors_min = mode_data["colors_min"]
        mode.colors_max = mode_data["colors_max"]
        mode.speed = mode_data["speed"]
        mode.brightness = mode_data["brightness"]
        mode.direction = mode_data["direction"]
        mode.color_mode = mode_data["color_mode"]
        mode.colors = (
            [RGBColor(*color) for color in mode_data["colors"]]
            if mode_data["colors"]
            else []
        )
        modes.append(mode)
    device.modes = modes

    # Zones
    zones = []
    for zone_data in mock_device_data["zones"]:
        zone = MagicMock()
        zone.name = zone_data["name"]
        zone.type = MagicMock()
        zone.type.name = zone_data["type"]
        zones.append(zone)
    device.zones = zones

    # LEDs
    leds = []
    for led_data in mock_device_data["leds"]:
        led = MagicMock()
        led.name = led_data["name"]
        leds.append(led)
    device.leds = leds

    # Colors
    device.colors = [RGBColor(*color) for color in mock_device_data["colors"]]

    # Methods
    device.set_color = MagicMock()
    device.set_mode = MagicMock()

    return device


@pytest.fixture
def mock_openrgb_client(mock_openrgb_device: MagicMock) -> Generator[MagicMock]:
    """Return a mocked OpenRGB client."""
    with (
        patch(
            "homeassistant.components.openrgb.coordinator.OpenRGBClient",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.openrgb.config_flow.OpenRGBClient",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value
        client.devices = [mock_openrgb_device]
        client.protocol_version = 4
        client.update = MagicMock()
        client.disconnect = MagicMock()

        # Store the class mock so tests can set side_effect
        client.client_class_mock = client_mock

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> MockConfigEntry:
    """Set up the OpenRGB integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
