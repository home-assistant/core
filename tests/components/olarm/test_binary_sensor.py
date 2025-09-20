"""Test the Olarm binary sensors."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.olarm.binary_sensor import (
    OlarmBinarySensor,
    load_ac_power_sensor,
    load_zone_sensors,
)
from homeassistant.components.olarm.coordinator import OlarmDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
async def setup_integration(hass: HomeAssistant):
    """Set up the integration."""
    config_entry = MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
            "load_zones_bypass_entities": False,
            "auth_implementation": "olarm",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9999999999,
            },
        },
    )
    config_entry.add_to_hass(hass)

    # Mock the coordinator data
    mock_coordinator = AsyncMock(spec=OlarmDataUpdateCoordinator)

    # Create a mock data object
    mock_data = AsyncMock()
    mock_data.device_state = {
        "zones": ["a", "c", "b"],  # active, closed, bypassed
        "powerAC": "ok",
    }
    mock_data.device_profile = {
        "zonesLabels": ["Front Door", "Window", "Motion"],
        "zonesTypes": [10, 11, 20],  # door, window, motion
    }
    mock_coordinator.data = mock_data

    return config_entry, mock_coordinator


async def test_zone_sensors(hass: HomeAssistant, setup_integration) -> None:
    """Test zone sensors creation and state."""
    config_entry, mock_coordinator = setup_integration

    # Test that sensors are created with correct states
    # Zone 0: active (should be ON)
    # Zone 1: closed (should be OFF)
    # Zone 2: bypassed (should be OFF for zone sensor)

    sensors: list[OlarmBinarySensor] = []
    load_zone_sensors(mock_coordinator, config_entry, sensors)

    # Should create 6 sensors (3 zones + 3 bypass)
    assert len(sensors) == 6

    # Check zone 0 (active)
    zone_0 = sensors[0]
    assert zone_0._attr_translation_key == "zone"
    assert zone_0._attr_is_on is True
    assert zone_0.entity_description.key == "zone"

    # Check zone 1 (closed)
    zone_1 = sensors[2]
    assert zone_1._attr_translation_key == "zone"
    assert zone_1._attr_is_on is False

    # Check zone 2 (bypassed - still OFF for zone sensor)
    zone_2 = sensors[4]
    assert zone_2._attr_translation_key == "zone"
    assert zone_2._attr_is_on is False


async def test_ac_power_sensor(hass: HomeAssistant, setup_integration) -> None:
    """Test AC power sensor creation and state."""
    config_entry, mock_coordinator = setup_integration

    sensors: list[OlarmBinarySensor] = []
    load_ac_power_sensor(mock_coordinator, config_entry, sensors)

    # Should create 1 AC power sensor
    assert len(sensors) == 1

    ac_sensor = sensors[0]
    assert ac_sensor._attr_translation_key == "ac_power"
    assert ac_sensor._attr_is_on is True
    assert ac_sensor.entity_description.key == "ac_power"
