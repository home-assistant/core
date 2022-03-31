"""Tests for the diagnostics data provided by the PVOutput integration."""
from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
):
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "energy_consumption": 1000,
        "energy_generation": 500,
        "normalized_output": 0.5,
        "power_consumption": 2500,
        "power_generation": 1500,
        "reported_date": "2021-12-29",
        "reported_time": "22:37:00",
        "temperature": 20.2,
        "voltage": 220.5,
    }
