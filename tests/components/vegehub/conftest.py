"""Fixtures and test data for VegeHub test methods."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from vegehub import VegeHub

from homeassistant.components.vegehub.coordinator import VegeHubCoordinator
from homeassistant.core import HomeAssistant

from tests.common import load_fixture

IP_ADDR = "192.168.0.100"
TEST_API_KEY = "1234567890ABCD"
UNIQUE_ID = "aabbccddeeff"
TEST_SERVER = "http://example.com"
TEST_MAC = "A1:B2:C3:D4:E5:F6"
TEST_SIMPLE_MAC = "A1B2C3D4E5F6"


@dataclass
class VegeHubData:
    """Define a data class."""

    coordinator: VegeHubCoordinator
    hub: VegeHub


@pytest.fixture
def mock_vegehub():
    """Mock the VegeHub library."""
    with patch(
        "homeassistant.components.vegehub.config_flow.VegeHub", autospec=True
    ) as mock_vegehub_class:
        mock_instance = MagicMock()
        # Simulate successful API calls
        mock_instance.retrieve_mac_address = AsyncMock(return_value=True)
        mock_instance.setup = AsyncMock(return_value=True)

        # Mock properties
        type(mock_instance).ip_address = PropertyMock(return_value=IP_ADDR)
        type(mock_instance).mac_address = PropertyMock(return_value=TEST_SIMPLE_MAC)
        type(mock_instance).unique_id = PropertyMock(return_value=UNIQUE_ID)
        type(mock_instance).url = PropertyMock(return_value=f"http://{IP_ADDR}")
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
def fixture_mocked_hub(mock_vegehub):
    """Fixture for creating a mocked VegeHub instance."""
    return mock_vegehub


@pytest.fixture
def config_entry(mocked_hub, hass: HomeAssistant):
    """Mock a config entry."""
    return MagicMock(
        data={"mac": "1234567890AB", "host": "VegeHub1"},
        runtime_data=VegeHubData(
            coordinator=VegeHubCoordinator(hass=hass, device_id=UNIQUE_ID),
            hub=mocked_hub,
        ),
    )
