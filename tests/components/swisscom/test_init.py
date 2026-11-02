"""Tests for the Swisscom Internet-Box integration setup."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from swisscom_internet_box import SwisscomAuthError, SwisscomConnectionError

from homeassistant.components.swisscom.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    mock_swisscom_client.get_devices.side_effect = SwisscomAuthError("Unauthorized")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_setup_connection_error_retries(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a connection error during setup schedules a retry."""
    mock_swisscom_client.get_devices.side_effect = SwisscomConnectionError("timeout")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_update_auth_error_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an authentication error during a scheduled refresh starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()

    mock_swisscom_client.get_devices.side_effect = SwisscomAuthError("Unauthorized")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
