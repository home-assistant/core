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
            "value_key": "1",
            "type": "temperature",
            "data_type": "temperature",
            "unit": "°C",
        },
        {
            "item_id": "2",
            "value_key": "1",
            "type": "temperature",
            "data_type": "temperature",
            "name": "Custom Temperature",
            "unit": "°C",
        },
        {
            "item_id": "3",
            "value_key": "1",
            "type": "battery",
            "data_type": "battery",
            "name": "Battery 1",
            "unit": "%",
        },
        {
            "item_id": "4",
            "value_key": "1",
            "type": "signal_strength",
            "data_type": "signal_strength",
            "name": "Signal 1",
            "unit": "dBm",
        },
        {
            "item_id": "5",
            "value_key": "1",
            "type": "dew_point",
            "data_type": "dew_point",
            "unit": "°C",
        },
        {
            "item_id": "6",
            "value_key": "1",
            "type": "unknown",
            "data_type": "unsupported_type_xyz",
            "unit": "",
        },
    ]

    device.parse_fresh_data = AsyncMock(
        return_value={
            "temperature": {"1": 22.5},
            "battery": {"3": 99},
            "signal_strength": {"4": -70},
            "dew_point": {"5": 10.0},
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
        mock_client.get_device_info = AsyncMock(
            return_value=("Test Papouch", "Test Lab")
        )
        yield mock_client, mock_create, mock_papouch_device
