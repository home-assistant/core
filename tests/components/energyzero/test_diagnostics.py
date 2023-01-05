"""Tests for the diagnostics data provided by the EnergyZero integration."""
from aiohttp import ClientSession
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


@pytest.mark.freeze_time("2022-12-07 15:00:00")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "entry": {
            "title": "energy",
        },
        "energy": {
            "current_hour_price": 0.49,
            "next_hour_price": 0.55,
            "average_price": 0.37,
            "max_price": 0.55,
            "min_price": 0.26,
            "highest_price_time": "2022-12-07T16:00:00+00:00",
            "lowest_price_time": "2022-12-07T02:00:00+00:00",
            "percentage_of_max": 89.09,
        },
        "gas": {
            "current_hour_price": 1.47,
            "next_hour_price": 1.47,
        },
    }
