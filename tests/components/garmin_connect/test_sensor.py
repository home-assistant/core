"""Tests for Garmin Connect sensor platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


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
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Check steps sensor
        state = hass.states.get("sensor.garmin_connect_steps")
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
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Test floors ascended
        state = hass.states.get("sensor.garmin_connect_floors_ascended")
        assert state is not None
        assert state.state == "10"

        # Test body battery
        state = hass.states.get("sensor.garmin_connect_body_battery")
        assert state is not None
        assert state.state == "80"

        # Test stress level
        state = hass.states.get("sensor.garmin_connect_average_stress_level")
        assert state is not None
        assert state.state == "30"


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
        mock_client.fetch_core_data = AsyncMock(side_effect=UpdateFailed("API Error"))

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should be in setup retry when coordinator fails on first refresh
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
