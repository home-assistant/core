"""Test the Vitesy integration setup and teardown."""

from unittest.mock import AsyncMock

from aiovitesy.exceptions import CannotAuthenticate, CannotConnect, VitesyError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.vitesy.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


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


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejected credentials put the entry in an error state."""
    mock_vitesy_client.login.side_effect = CannotAuthenticate
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed refresh marks the entities unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_vitesy_client.get_all_devices.side_effect = VitesyError("boom")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.kitchen_shelfy_air_quality_score").state
        == STATE_UNAVAILABLE
    )


async def test_update_auth_failure(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test rejected credentials during a refresh keep the coordinator polling."""
    await setup_integration(hass, mock_config_entry)

    mock_vitesy_client.get_all_devices.side_effect = CannotAuthenticate
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_vitesy_client.get_all_devices.side_effect = None
    mock_vitesy_client.get_all_devices.return_value = {}
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.last_update_success
