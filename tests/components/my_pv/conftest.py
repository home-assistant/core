"""Common fixtures for the my-PV tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from . import ELWA2_SERIAL_NUMBER

from tests.common import MockConfigEntry

SETUP_CONFIGURATION = {
    "ww1target": {"step": 0.1, "unit": "°C", "min": 5.0, "max": 95.0}
}

DATA_CONFIGURATION = {
    "cur_eth_mode": {
        "options": {"0": "LAN", "1": "WLAN", "2": "AP"},
        "type": "enumeration",
    },
    "freq": {"type": "number", "unit": "Hz"},
    "power": {"type": "number", "unit": "W"},
    "screen_mode_flag": {
        "options": {
            "0": "Standby",
            "1": "Heat",
            "2": "Boost",
            "3": "Heating finished",
            "4": "No connection / Disabled",
            "5": "Error",
            "6": "Block active",
        },
        "type": "enumeration",
    },
    "temp1": {"type": "number", "unit": "°C"},
    "temp2": {"type": "number", "unit": "°C"},
    "temp3": {"type": "number", "unit": "°C"},
    "temp4": {"type": "number", "unit": "°C"},
    "temp_ps": {"type": "number", "unit": "°C"},
    "uptime": {"type": "number", "unit": "h"},
    "volt_mains": {"type": "number", "unit": "V"},
}

DATA_VALUE = {
    "cur_eth_mode": "0",
    "freq": 49.965,
    "power": 3445,
    "screen_mode_flag": "4",
    "temp1": 12.3,
    "temp2": 23.4,
    "temp3": 34.5,
    "temp4": 45.6,
    "temp_ps": 56.7,
    "uptime": 2,
    "volt_mains": 238,
}


def _setup_configuration_lookup(key):
    return SETUP_CONFIGURATION.get(key)


def _data_value_lookup(key):
    return DATA_VALUE.get(key)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the my-PV mocked config entry for local devices."""
    return MockConfigEntry(
        title="my-PV AC ELWA 2 0000000000",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id=ELWA2_SERIAL_NUMBER,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent running the real integration setup during tests."""
    with patch(
        "homeassistant.components.my_pv.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_my_pv_client() -> Generator[AsyncMock]:
    """Mock the my-PV client across the integration."""
    with (
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.my_pv.coordinator.MyPVDevice",
            new=mock_client,
        ) as mock_client,
        patch(
            "homeassistant.components.my_pv.config_flow.MyPVLocalDevice",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.connect = AsyncMock(return_value=True)
        client.disconnect = AsyncMock(return_value=True)
        client.serial_number = ELWA2_SERIAL_NUMBER
        client.model = "AC ELWA 2"
        client.mac_address = "98:6d:35:c0:00:00"
        client.setup_uri = "http://127.0.0.1/"
        client.hardware_version = "v1.5A"
        client.firmware_version = "e0002200"
        client.current_temperature = 54.3
        client.target_temperature = 62.1
        client.get_setup_configuration = Mock(side_effect=_setup_configuration_lookup)
        client.get_data_configurations = Mock(return_value=DATA_CONFIGURATION)
        client.get_data_value = Mock(side_effect=_data_value_lookup)

        yield client
