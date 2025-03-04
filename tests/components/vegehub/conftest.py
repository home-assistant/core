"""Fixtures and test data for VegeHub test methods."""

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from vegehub import VegeHub

from homeassistant.components.vegehub.coordinator import VegeHubCoordinator
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_IP = "192.168.0.100"
TEST_UNIQUE_ID = "aabbccddeeff"
TEST_SERVER = "http://example.com"
TEST_MAC = "A1:B2:C3:D4:E5:F6"
TEST_SIMPLE_MAC = "A1B2C3D4E5F6"
TEST_HOSTNAME = "VegeHub"
TEST_WEBHOOK_ID = "webhook_id"
HUB_DATA = {
    "first_boot": False,
    "page_updated": False,
    "error_message": 0,
    "num_channels": 2,
    "num_actuators": 2,
    "version": "3.4.5",
    "agenda": 1,
    "batt_v": 9.0,
    "num_vsens": 0,
    "is_ac": 0,
    "has_sd": 0,
    "on_ap": 0,
}


@dataclass
class VegeHubData:
    """Define a data class."""

    coordinator: VegeHubCoordinator
    hub: VegeHub


@pytest.fixture
def mock_vegehub() -> Generator[Any, Any, Any]:
    """Mock the VegeHub library."""
    with patch(
        "homeassistant.components.vegehub.config_flow.VegeHub", autospec=True
    ) as mock_vegehub_class:
        mock_instance = mock_vegehub_class.return_value
        # Simulate successful API calls
        mock_instance.retrieve_mac_address = AsyncMock(return_value=True)
        mock_instance.setup = AsyncMock(return_value=True)

        # Mock properties
        type(mock_instance).ip_address = PropertyMock(return_value=TEST_IP)
        type(mock_instance).mac_address = PropertyMock(return_value=TEST_SIMPLE_MAC)
        type(mock_instance).unique_id = PropertyMock(return_value=TEST_UNIQUE_ID)
        type(mock_instance).url = PropertyMock(return_value=f"http://{TEST_IP}")
        type(mock_instance).info = PropertyMock(
            return_value=load_fixture("vegehub/info_hub.json")
        )
        type(mock_instance).num_sensors = PropertyMock(return_value=2)
        type(mock_instance).num_actuators = PropertyMock(return_value=2)
        type(mock_instance).sw_version = PropertyMock(return_value="3.4.5")

        # Assign the instance to the mocked class
        mock_vegehub_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture(name="mocked_hub")
def fixture_mocked_hub(mock_vegehub: MagicMock) -> MagicMock:
    """Fixture for creating a mocked VegeHub instance."""
    return mock_vegehub


@pytest.fixture(name="mocked_config_entry")
async def fixture_mocked_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock VegeHub config entry."""
    return MockConfigEntry(
        domain="vegehub",
        data={
            CONF_MAC: TEST_SIMPLE_MAC,
            CONF_IP_ADDRESS: TEST_IP,
            CONF_HOST: TEST_HOSTNAME,
            CONF_DEVICE: HUB_DATA,
            CONF_WEBHOOK_ID: TEST_WEBHOOK_ID,
        },
        unique_id=TEST_SIMPLE_MAC,
        title="VegeHub",
        entry_id="12345",
    )
