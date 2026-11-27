"""Tests for the Electricity Maps integration setup."""

from unittest.mock import AsyncMock

from aioelectricitymaps import ElectricityMapsInvalidTokenError
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    electricity_maps: AsyncMock,
) -> None:
    """Test a rejected API key during setup starts reauth without retrying."""
    electricity_maps.carbon_intensity_for_home_assistant.side_effect = (
        ElectricityMapsInvalidTokenError
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert (flows := hass.config_entries.flow.async_progress())
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
