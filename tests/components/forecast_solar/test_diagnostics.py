"""Tests for the diagnostics data provided by the Forecast.Solar integration."""
from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
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
        "entry": {
            "title": "Green House",
            "data": {
                "latitude": REDACTED,
                "longitude": REDACTED,
            },
            "options": {
                "api_key": REDACTED,
                "azimuth": 190,
                "damping": 0.5,
                "declination": 30,
                "inverter_size": 2000,
                "modules power": 5100,
            },
        },
        "data": {
            "energy_production_today": 100000,
            "energy_production_tomorrow": 200000,
            "energy_current_hour": 800000,
            "power_production_now": 300000,
        },
        "account": {
            "type": "public",
            "rate_limit": 60,
            "timezone": "Europe/Amsterdam",
        },
    }
