"""Tests for Garmin Connect sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.garmin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            "oauth1_token": "mock_oauth1_token",
            "oauth2_token": "mock_oauth2_token",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_sensor_data() -> dict:
    """Return mock sensor data."""
    return {
        "totalSteps": 10000,
        "totalDistanceMeters": 8000.0,
        "activeKilocalories": 500,
        "restingHeartRate": 60,
        "minHeartRate": 50,
        "maxHeartRate": 150,
        "averageStressLevel": 30,
        "bodyBatteryMostRecentValue": 80,
        "bodyBatteryChargedValue": 40,
        "bodyBatteryDrainedValue": 20,
        "floorsAscended": 10,
        "floorsDescended": 5,
        "dailyStepGoal": 10000,
        "sleepingSeconds": 28800,
        "deepSleepSeconds": 7200,
        "lightSleepSeconds": 14400,
        "remSleepSeconds": 7200,
        "weight": 75000,  # In grams
        "bmi": 24.5,
        "hrvStatus": {
            "status": "BALANCED",
            "weeklyAvg": 45,
            "lastNightAvg": 42,
            "lastNight5MinHigh": 65,
            "baseline": {"lowUpper": 40, "balancedLow": 35, "balancedUpper": 55},
        },
        "lastActivity": {
            "activityId": 12345,
            "activityName": "Morning Run",
            "activityType": {"typeKey": "running"},
            "distance": 5000.0,
            "duration": 1800.0,
            "startTimeLocal": "2024-01-15T07:00:00",
            "averageHR": 145,
            "maxHR": 175,
            "calories": 400,
        },
        "lastActivities": [
            {"activityId": 12345, "activityName": "Morning Run"},
            {"activityId": 12344, "activityName": "Walk"},
        ],
        "gear": [
            {
                "uuid": "gear-uuid-1",
                "displayName": "Running Shoes",
                "gearStatusName": "active",
            }
        ],
        "gearStats": [
            {
                "uuid": "gear-uuid-1",
                "totalDistance": 500000.0,
                "totalActivities": 50,
            }
        ],
    }


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test sensor platform setup creates sensors."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.get_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Check total steps sensor
    state = hass.states.get("sensor.garmin_connect_total_steps")
    assert state is not None
    assert state.state == "10000"

    # Check resting heart rate sensor
    state = hass.states.get("sensor.garmin_connect_resting_heart_rate")
    assert state is not None
    assert state.state == "60"


async def test_sensor_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test sensor values are correctly extracted."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.get_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test floors ascended
    state = hass.states.get("sensor.garmin_connect_floors_ascended")
    assert state is not None
    assert state.state == "10"

    # Test body battery
    state = hass.states.get("sensor.garmin_connect_body_battery_most_recent")
    assert state is not None
    assert state.state == "80"

    # Test stress level
    state = hass.states.get("sensor.garmin_connect_avg_stress_level")
    assert state is not None
    assert state.state == "30"


async def test_hrv_sensor_with_value_fn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test HRV sensors that use value_fn."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.get_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test HRV status sensor (uses value_fn to extract nested status)
    state = hass.states.get("sensor.garmin_connect_hrv_status")
    assert state is not None
    assert state.state == "Balanced"

    # Test HRV weekly avg (uses value_fn)
    state = hass.states.get("sensor.garmin_connect_hrv_weekly_avg")
    assert state is not None
    assert state.state == "45"


async def test_last_activity_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test last activity sensor with attributes."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.get_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test last activity sensor
    state = hass.states.get("sensor.garmin_connect_last_activity")
    assert state is not None
    assert state.state == "Morning Run"
    # Check attributes exist
    assert state.attributes.get("activityId") == 12345


async def test_sensor_unavailable_when_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor shows unavailable when coordinator fails."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.get_data = AsyncMock(side_effect=UpdateFailed("API Error"))

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should still be loaded but sensors unavailable
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Sensors should be unavailable
    state = hass.states.get("sensor.garmin_connect_total_steps")
    if state:
        assert state.state == "unavailable"


async def test_weight_sensor_converts_grams_to_kg(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test weight sensor converts grams to kilograms."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.get_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test weight sensor (75000g -> 75.0kg)
    state = hass.states.get("sensor.garmin_connect_weight")
    assert state is not None
    assert state.state == "75.0"
