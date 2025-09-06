"""Test the AirPatrol data update coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock

from airpatrol.api import AirPatrolAuthenticationError, AirPatrolError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_update_data_with_stored_token(
    hass: HomeAssistant,
    mock_api_response: AsyncMock,
    mock_config_entry: MockConfigEntry,
    get_data,
) -> None:
    """Test data update with stored access token."""
    mock_api_response.return_value = get_data()
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api_response.assert_called()
    assert mock_api_response.call_count == 2
    state: State | None = hass.states.get("climate.living_room")
    assert state
    assert state.state == "cool"
    assert state.attributes["temperature"] == 22.0
    assert state.attributes["current_temperature"] == 22.5
    assert state.attributes["current_humidity"] == 45.0


async def test_update_data_refresh_token_success(
    hass: HomeAssistant,
    get_data,
    mock_config_entry: MockConfigEntry,
    mock_api_authentication: AsyncMock,
    mock_api_response: AsyncMock,
) -> None:
    """Test data update with expired token and successful token refresh."""
    mock_api_response.side_effect = [AirPatrolAuthenticationError("fail"), get_data()]
    mock_api_authentication.return_value.get_data = mock_api_response

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_api_response.call_count == 2

    state: State | None = hass.states.get("climate.living_room")
    assert state
    assert state.state == "cool"
    assert state.attributes["temperature"] == 22.0
    assert state.attributes["current_temperature"] == 22.5
    assert state.attributes["current_humidity"] == 45.0


async def test_update_data_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_authentication: AsyncMock,
    mock_api_response: AsyncMock,
) -> None:
    """Test permanent authentication failure."""
    mock_config_entry.add_to_hass(hass)
    mock_api_authentication.side_effect = AirPatrolAuthenticationError("fail")
    mock_api_response.side_effect = AirPatrolAuthenticationError("fail")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state: State | None = hass.states.get("climate.living_room")
    assert state is None

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Authentication with AirPatrol failed"


async def test_update_data_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_response: AsyncMock,
    freezer: FrozenDateTimeFactory,
    get_data,
) -> None:
    """Test API error handling."""
    mock_config_entry.add_to_hass(hass)

    mock_api_response.side_effect = [get_data(), get_data(), AirPatrolError("fail")]
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_api_response.call_count == 3
    state: State | None = hass.states.get("climate.living_room")
    assert state
    assert state.state == "unavailable"


async def test_update_data_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_authentication: AsyncMock,
    mock_api_response: AsyncMock,
    get_data,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test authentication error handling on data update."""
    mock_config_entry.add_to_hass(hass)
    mock_api_authentication.side_effect = AirPatrolAuthenticationError("fail")
    mock_api_response.side_effect = [
        get_data(),
        get_data(),
        AirPatrolAuthenticationError("fail"),
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)

    state: State | None = hass.states.get("climate.living_room")
    assert state
    assert state.state == "unavailable"
