"""Tests for the diagnostics data provided by the Forecast.Solar integration."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
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
                "declination": 30,
                "azimuth": 190,
                "modules_power": 5100,
                "damping_evening": 0.5,
                "damping_morning": 0.5,
                "inverter_size": 2000,
            },
        },
        "data": {
            "energy_production_today": 100000,
            "energy_production_today_remaining": 50000,
            "energy_production_tomorrow": 200000,
            "energy_current_hour": 800000,
            "power_production_now": 300000,
            "watts": {
                "2021-06-27T13:00:00-07:00": 10,
                "2022-06-27T13:00:00-07:00": 100,
            },
            "wh_days": {
                "2021-06-27T13:00:00-07:00": 20,
                "2022-06-27T13:00:00-07:00": 200,
            },
            "wh_period": {
                "2021-06-27T13:00:00-07:00": 30,
                "2022-06-27T13:00:00-07:00": 300,
            },
        },
        "account": {
            "type": "public",
            "rate_limit": 60,
            "timezone": "Europe/Amsterdam",
        },
    }
