"""Test the AirPatrol integration setup."""

from unittest.mock import patch

from airpatrol.api import AirPatrolAPI, AirPatrolAuthenticationError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    get_client: AirPatrolAPI,
) -> None:
    """Test loading and unloading the config entry."""
    # Add the config entry to hass first
    mock_config_entry.add_to_hass(hass)

    # Load the config entry
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_update_data_refresh_token_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    get_client: AirPatrolAPI,
    get_data,
) -> None:
    """Test data update with expired token and successful token refresh."""
    get_client.get_data.side_effect = [
        AirPatrolAuthenticationError("fail"),
        get_data,
    ]

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert get_client.get_data.call_count == 2

    assert hass.states.get("climate.living_room")


async def test_update_data_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    get_client: AirPatrolAPI,
) -> None:
    """Test permanent authentication failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airpatrol.coordinator.AirPatrolAPI.authenticate",
        side_effect=AirPatrolAuthenticationError("fail"),
    ):
        get_client.get_data.side_effect = AirPatrolAuthenticationError("fail")

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        state: State | None = hass.states.get("climate.living_room")
        assert state is None

        entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert entry.reason == "Authentication with AirPatrol failed"
