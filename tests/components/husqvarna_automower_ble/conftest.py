"""Common fixtures for the Husqvarna Automower Bluetooth tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.husqvarna_automower_ble.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_CLIENT_ID

from . import AUTOMOWER_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.husqvarna_automower_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_automower_client(enable_bluetooth: None) -> Generator[AsyncMock]:
    """Mock a BleakClient client."""
    with (
        patch(
            "homeassistant.components.husqvarna_automower_ble.Mower",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.husqvarna_automower_ble.config_flow.Mower",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.connect.return_value = True
        client.is_connected.return_value = True
        client.get_model.return_value = "305"
        client.battery_level.return_value = 100
        client.mower_state.return_value = "pendingStart"
        client.mower_activity.return_value = "charging"
        client.probe_gatts.return_value = ("Husqvarna", "Automower", "305")

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Husqvarna AutoMower",
        data={
            CONF_ADDRESS: AUTOMOWER_SERVICE_INFO.address,
            CONF_CLIENT_ID: 1197489078,
        },
        unique_id=AUTOMOWER_SERVICE_INFO.address,
    )
