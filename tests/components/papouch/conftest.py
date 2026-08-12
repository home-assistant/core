"""Common fixtures for the Papouch tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.papouch.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Papouch (192.168.1.50)",
        data={"ip_address": "192.168.1.50", "password": "pass"},
        unique_id="00:11:22:33:44:55",
    )


@pytest.fixture
def mock_papouch_device():
    """Mock a Papouch device instance with all supported entities."""
    device = MagicMock()
    device.mac_address = "00:11:22:33:44:55"
    device.name = "Test Papouch"
    device.manufacturer = "Papouch s.r.o."
    device.location = "Test Lab"

    device.get_supported_sensors.return_value = [
        {
            "item_id": "1",
            "type": "temperature",
            "name": "Temp 1",
            "unit": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
            "icon": "mdi:thermometer",
        }
    ]
    device.get_supported_binary_sensors.return_value = [
        {
            "item_id": "1",
            "type": "input",
            "name": "Input 1",
            "device_class": "door",
            "icon": "mdi:door-open",
        }
    ]
    device.get_supported_switches.return_value = [
        {"item_id": "1", "name": "Switch 1", "icon": "mdi:toggle-switch"}
    ]
    device.get_supported_buttons.return_value = [
        {"cmd": "reset", "name": "Reset", "icon": "mdi:restart"}
    ]
    device.get_supported_numbers.return_value = [
        {
            "item_id": "1",
            "category": "limit",
            "name": "Limit 1",
            "mode": "box",
            "min_value": 0,
            "max_value": 100,
            "step": 1,
            "icon": "mdi:numeric",
        }
    ]
    device.get_supported_selects.return_value = [
        {
            "item_id": "1",
            "category": "mode",
            "name": "Mode 1",
            "options": ["A", "B"],
            "icon": "mdi:format-list-bulleted",
        }
    ]

    device.parse_fresh_data = AsyncMock(
        return_value={
            "temperature": {"1": 22.5},
            "input": {"1": 1},
            "switch": {"1": 1},
        }
    )

    device.turn_on_switch = AsyncMock()
    device.turn_off_switch = AsyncMock()
    device.execute_button_command = AsyncMock()
    device.set_number_value = AsyncMock()
    device.set_select_option = AsyncMock()
    device.get_select_option.return_value = "A"

    return device


@pytest.fixture
def mock_papouch_client(mock_papouch_device):
    """Mock the Papouch API client and device factory."""
    with (
        patch("homeassistant.components.papouch.PapouchHTTPClient") as mock_client_cls,
        patch(
            "homeassistant.components.papouch.create_device",
            return_value=mock_papouch_device,
        ) as mock_create,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.ip_address = "192.168.1.50"
        mock_client.fetch_data = AsyncMock(return_value="<xml>fresh</xml>")
        yield mock_client, mock_create, mock_papouch_device
