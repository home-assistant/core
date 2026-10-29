"""Tests for aerosmart diagnostics."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aerosmart.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def test_diagnostics_redacts_connection_and_summarizes_updates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Diagnostics redact the endpoint while retaining useful update state."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry_data"]["host"] == "**REDACTED**"
    assert "outside_temperature" in diagnostics["readings"]["updated_components"]
    assert diagnostics["readings"]["failed_components"] == []
    assert "fine_dust_filter" in diagnostics["settings"]["updated_components"]
    assert diagnostics["settings"]["failed_components"] == []
