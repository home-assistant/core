"""Tests for aerosmart diagnostics."""

from homeassistant.components.aerosmart.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics_report_both_poll_categories(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostics expose poll health without issuing another Modbus read."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await mock_config_entry.runtime_data.async_wait_initial_refresh()

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["initial_refresh_completed"] is True
    assert result["polls"]["readings"]["last_update_success"] is True
    assert result["polls"]["settings"]["last_update_success"] is True
    assert "heat_pump" in result["polls"]["readings"]["updated"]
    assert "fine_dust_filter" in result["polls"]["settings"]["updated"]
    assert result["polls"]["readings"]["failed"] == []
    assert result["polls"]["settings"]["failed"] == []
    assert result["registers"]["general_wochentag"] == 3
