"""Test the Olarm coordinator."""

from unittest.mock import AsyncMock

from olarmflowclient import OlarmFlowClientApiError
import pytest

from homeassistant.components.olarm.coordinator import (
    OlarmDataUpdateCoordinator,
    OlarmDeviceData,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import MOCK_DEVICE_RESPONSE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
        },
    )


@pytest.fixture
def mock_oauth_session():
    """Create a mock OAuth session."""
    return AsyncMock()


@pytest.fixture
def mock_olarm_client():
    """Create a mock Olarm client."""
    return AsyncMock()


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_config_entry, mock_oauth_session, mock_olarm_client
):
    """Create a coordinator instance."""
    return OlarmDataUpdateCoordinator(
        hass, mock_config_entry, mock_oauth_session, mock_olarm_client
    )


async def test_coordinator_init(coordinator, mock_config_entry) -> None:
    """Test coordinator initialization."""
    assert coordinator.device_id == "test-device-id"
    assert coordinator.name == "olarm_test-device-id"


async def test_coordinator_update_success(coordinator, mock_olarm_client) -> None:
    """Test successful data update."""
    mock_olarm_client.get_device.return_value = MOCK_DEVICE_RESPONSE

    data = await coordinator._async_update_data()

    assert isinstance(data, OlarmDeviceData)
    assert data.device_name == "Test Device"
    assert data.device_state == {
        "zones": ["a", "c", "b"],
        "powerAC": "ok",
    }
    assert data.device_profile == {
        "zonesLabels": ["Front Door", "Window", "Motion"],
        "zonesTypes": [10, 11, 20],
    }
    assert data.device_links == {}
    mock_olarm_client.get_device.assert_called_once_with("test-device-id")


async def test_coordinator_update_failure(coordinator, mock_olarm_client) -> None:
    """Test failed data update."""
    mock_olarm_client.get_device.side_effect = OlarmFlowClientApiError("API Error")

    with pytest.raises(UpdateFailed, match="Failed to reach Olarm API"):
        await coordinator._async_update_data()


async def test_coordinator_update_from_mqtt(coordinator, mock_olarm_client) -> None:
    """Test updating data from MQTT."""
    # First set initial data
    mock_olarm_client.get_device.return_value = MOCK_DEVICE_RESPONSE
    data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(data)

    # Mock MQTT payload
    mqtt_payload = {
        "deviceState": {
            "zones": ["a", "c", "b"],
            "powerAC": "ok",
        },
        "deviceLinks": {},
        "deviceIO": {},
    }

    # Update from MQTT
    coordinator.async_update_from_mqtt(mqtt_payload)

    # Verify data was updated
    assert coordinator.data.device_state == {
        "zones": ["a", "c", "b"],
        "powerAC": "ok",
    }
    assert coordinator.data.device_links == {}
    assert coordinator.data.device_io == {}


async def test_coordinator_properties(coordinator, mock_olarm_client) -> None:
    """Test coordinator data access."""
    # Test when no data
    assert coordinator.data is None

    # Set some data
    mock_olarm_client.get_device.return_value = MOCK_DEVICE_RESPONSE
    data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(data)

    # Test data access
    assert coordinator.data.device_name == "Test Device"
    assert coordinator.data.device_state == {
        "zones": ["a", "c", "b"],
        "powerAC": "ok",
    }
    assert coordinator.data.device_links == {}
    assert coordinator.data.device_io == {}
    assert coordinator.data.device_profile == {
        "zonesLabels": ["Front Door", "Window", "Motion"],
        "zonesTypes": [10, 11, 20],
    }
    assert coordinator.data.device_profile_links == {}
    assert coordinator.data.device_profile_io == {}


async def test_coordinator_mqtt_update_no_data(coordinator) -> None:
    """Test MQTT update when coordinator has no data."""
    # Should not crash when no data exists
    coordinator.async_update_from_mqtt({"deviceState": {"status": "armed"}})

    # Data should still be None
    assert coordinator.data is None


async def test_device_data_defaults() -> None:
    """Test OlarmDeviceData with defaults."""
    data = OlarmDeviceData(device_name="Test Device")

    assert data.device_name == "Test Device"
    assert data.device_state is None
    assert data.device_links is None
    assert data.device_io is None
    assert data.device_profile is None
    assert data.device_profile_links is None
    assert data.device_profile_io is None
