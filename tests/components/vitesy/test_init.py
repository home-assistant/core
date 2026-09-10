"""Test the Vitesy integration setup and teardown."""

from unittest.mock import AsyncMock

from aiovitesy.exceptions import CannotAuthenticate, CannotConnect, VitesyError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejected credentials put the entry in an error state and ask for reauth."""
    mock_vitesy_client.login.side_effect = CannotAuthenticate
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_setup_connection_failure_is_retried(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a transient connection error triggers a setup retry."""
    mock_vitesy_client.login.side_effect = CannotConnect
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed refresh marks the entities unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_vitesy_client.get_all_devices.side_effect = VitesyError("boom")
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.kitchen_shelfy_air_quality_score").state
        == STATE_UNAVAILABLE
    )


async def test_update_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejected credentials during a refresh trigger the reauth flow."""
    await setup_integration(hass, mock_config_entry)

    mock_vitesy_client.get_all_devices.side_effect = CannotAuthenticate
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))
