"""Test setup and unloading of the Monarch Money integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_unload_and_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading stops polling and restores sensors on reload."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    initial_state = hass.states.get("sensor.cashflow_expense_year_to_date")
    assert initial_state is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get("sensor.cashflow_expense_year_to_date")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["restored"] is True
    mock_config_api.return_value.reset_mock()

    freezer.tick(timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_config_api.return_value.get_accounts_as_dict_with_id_key.assert_not_awaited()
    mock_config_api.return_value.get_cashflow_summary.assert_not_awaited()
    mock_config_api.return_value.get_budgets_as_dict_with_id_key.assert_not_awaited()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("sensor.cashflow_expense_year_to_date")
    assert state is not None
    assert state.state == initial_state.state
    assert "restored" not in state.attributes
    mock_config_api.return_value.get_accounts_as_dict_with_id_key.assert_awaited_once()
    mock_config_api.return_value.get_cashflow_summary.assert_awaited_once()
    mock_config_api.return_value.get_budgets_as_dict_with_id_key.assert_awaited_once()
