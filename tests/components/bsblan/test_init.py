"""Tests for the BSBLan integration."""

from unittest.mock import MagicMock

from bsblan import BSBLANAuthError, BSBLANConnectionError, BSBLANError
from freezegun.api import FrozenDateTimeFactory
import pytest

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
    # The coordinator calls state(), sensor(), and hot_water_state() during updates
    mock_bsblan.state.side_effect = BSBLANAuthError("Authentication failed")

    # Advance time by the coordinator's update interval to trigger update
    freezer.tick(delta=20)  # Advance beyond the 12 second scan interval + random offset
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Check that a reauth flow has been started
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("method", "exception", "expected_state"),
    [
        (
            "device",
            BSBLANConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            "info",
            BSBLANAuthError("Authentication failed"),
            ConfigEntryState.SETUP_ERROR,
        ),
        ("static_values", BSBLANError("General error"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_config_entry_static_data_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    method: str,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test various errors during static data fetching trigger appropriate config entry states."""
    # Mock the specified method to raise the exception
    getattr(mock_bsblan, method).side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_coordinator_dhw_config_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handling when DHW config update fails but keeps existing data."""
    # First, set up the integration successfully
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Mock DHW config methods to fail, but keep state/sensor working
    mock_bsblan.hot_water_config.side_effect = BSBLANConnectionError("Config failed")
    mock_bsblan.hot_water_schedule.side_effect = BSBLANAuthError("Schedule failed")

    # Advance time by 5+ minutes to trigger config update (slow polling)
    freezer.tick(delta=301)  # 5 minutes + 1 second
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The coordinator should still be working despite config update failures
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify the error handling paths were executed
    assert mock_bsblan.hot_water_config.called
    assert mock_bsblan.hot_water_schedule.called


async def test_coordinator_slow_first_fetch_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test slow coordinator when first fetch fails."""
    # Make slow coordinator fail on first fetch
    mock_bsblan.hot_water_config.side_effect = BSBLANConnectionError("Config failed")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still load even if slow coordinator fails
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify slow coordinator was called and handled the error gracefully
    assert mock_bsblan.hot_water_config.called


async def test_config_entry_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test TimeoutError during setup raises ConfigEntryNotReady."""
    mock_bsblan.initialize.side_effect = TimeoutError("Connection timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Should be in retry state due to timeout
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_slow_no_dhw_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bsblan: MagicMock,
) -> None:
    """Test slow coordinator when device does not support DHW (AttributeError)."""
    # Mock that device doesn't support DHW - raises AttributeError
    mock_bsblan.hot_water_config.side_effect = AttributeError(
        "Device does not support DHW"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Integration should still load even if DHW is not supported
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify slow coordinator handled the AttributeError gracefully
    assert mock_bsblan.hot_water_config.called
