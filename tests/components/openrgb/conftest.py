"""Fixtures for OpenRGB integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openrgb.utils import DeviceType, ModeFlags, RGBColor
import pytest

from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OpenRGB (127.0.0.1:6742)",
        data={
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
    """Return mock device data for creating OpenRGB devices."""
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
        "active_mode": 0,
        "modes": [
            {
                "name": "Direct",
                "value": 0,
                "flags": ModeFlags.HAS_PER_LED_COLOR,
                "speed_min": 0,
                "speed_max": 0,
                "brightness_min": 0,
                "brightness_max": 0,
                "colors_min": 0,
                "colors_max": 0,
                "speed": 0,
                "brightness": 0,
                "direction": 0,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Static",
                "value": 1,
                "flags": ModeFlags.HAS_PER_LED_COLOR,
                "speed_min": 0,
                "speed_max": 0,
                "brightness_min": 0,
                "brightness_max": 0,
                "colors_min": 0,
                "colors_max": 0,
                "speed": 0,
                "brightness": 0,
                "direction": 0,
                "color_mode": 1,
                "colors": [],
            },
            {
                "name": "Rainbow",
                "value": 2,
                "flags": 0,  # No color support
                "speed_min": 0,
                "speed_max": 100,
                "brightness_min": 0,
                "brightness_max": 0,
                "colors_min": 0,
                "colors_max": 0,
                "speed": 50,
                "brightness": 0,
                "direction": 0,
                "color_mode": 0,
                "colors": [],
            },
            {
                "name": "Off",
                "value": 3,
                "flags": 0,
                "speed_min": 0,
                "speed_max": 0,
                "brightness_min": 0,
                "brightness_max": 0,
                "colors_min": 0,
                "colors_max": 0,
                "speed": 0,
                "brightness": 0,
                "direction": 0,
                "color_mode": 0,
                "colors": [],
            },
        ],
        "zones": [],
        "leds": [
            {"name": "LED 1", "value": 0},
            {"name": "LED 2", "value": 1},
        ],
        "colors": [(255, 0, 0), (255, 0, 0)],  # Red
    }


@pytest.fixture
def mock_openrgb_device(mock_device_data: dict[str, Any]) -> MagicMock:
    """Return a mocked OpenRGB device."""
    device = MagicMock()
    device.id = 0
    device.name = mock_device_data["name"]
    device.type = MagicMock()
    device.type.name = "LEDSTRIP"
    device.type.value = mock_device_data["type"]

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
        modes.append(mode)
    device.modes = modes

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
        client.protocol_version = 3
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

    return mock_config_entry
