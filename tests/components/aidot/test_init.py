"""Test aidot."""

from unittest.mock import MagicMock

from aidot.exceptions import AidotAuthFailed, AidotUserOrPassIncorrect
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.aidot.coordinator import UPDATE_DEVICE_LIST_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that async_unload_entry unloads the component correctly."""
    await async_init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_aidot_client: MagicMock,
) -> None:
    """Test an auth error during setup starts a reauth flow."""
    patch_aidot_client.login_info = {}
    patch_aidot_client.async_post_login.side_effect = AidotUserOrPassIncorrect()

    await async_init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_first_refresh_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_aidot_client: MagicMock,
) -> None:
    """Test a rejected token during the first refresh starts a reauth flow."""
    patch_aidot_client.async_get_all_device.side_effect = AidotAuthFailed()

    await async_init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_scheduled_refresh_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_aidot_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected token during a scheduled refresh starts a reauth flow."""
    await async_init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    patch_aidot_client.async_get_all_device.side_effect = AidotAuthFailed()
    freezer.tick(UPDATE_DEVICE_LIST_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
