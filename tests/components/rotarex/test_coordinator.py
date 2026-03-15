"""Test the Rotarex coordinator effects on entities."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from rotarex_dimes_srg_api import InvalidAuth

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_rotarex_api")


async def test_setup_loads_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration loads and creates entities for all tanks."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.tank_1_level") is not None
    assert hass.states.get("sensor.tank_2_level") is not None


async def test_auth_failure_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test config entry enters error state on auth error during setup."""
    mock_rotarex_api.login.side_effect = InvalidAuth("Invalid credentials")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_connection_error_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test config entry enters retry state on connection error during setup."""
    mock_rotarex_api.login.side_effect = Exception("Connection error")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rotarex_api: AsyncMock,
) -> None:
    """Test that an update failure marks entities as unavailable."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    level_state = hass.states.get("sensor.tank_1_level")
    assert level_state is not None
    assert level_state.state == "70.0"

    # Simulate connection failure
    mock_rotarex_api.fetch_tanks.side_effect = Exception("Connection error")
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    level_state = hass.states.get("sensor.tank_1_level")
    assert level_state
    assert level_state.state == "unavailable"
