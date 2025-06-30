"""Fixtures and test data for VegeHub test methods."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

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


@pytest.fixture(autouse=True)
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
        mock_instance.ip_address = TEST_IP
        mock_instance.mac_address = TEST_SIMPLE_MAC
        mock_instance.unique_id = TEST_UNIQUE_ID
        mock_instance.url = f"http://{TEST_IP}"
        mock_instance.info = load_fixture("vegehub/info_hub.json")
        mock_instance.num_sensors = 2
        mock_instance.num_actuators = 2
        mock_instance.sw_version = "3.4.5"

        yield mock_instance


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
