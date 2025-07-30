"""Tests for the BSBLan integration."""

from unittest.mock import MagicMock

from bsblan import BSBLANAuthError, BSBLANConnectionError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the BSBLAN configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_bsblan.device.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test the bsblan configuration entry not ready."""
    mock_bsblan.state.side_effect = BSBLANConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_bsblan.state.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_failed_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that BSBLANAuthError during coordinator update triggers reauth flow."""
    # First, set up the integration successfully
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Mock BSBLANAuthError during next update
    mock_bsblan.initialize.side_effect = BSBLANAuthError("Authentication failed")

    # Advance time by the coordinator's update interval to trigger update
    freezer.tick(delta=20)  # Advance beyond the 12 second scan interval + random offset
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that a reauth flow has been started
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
