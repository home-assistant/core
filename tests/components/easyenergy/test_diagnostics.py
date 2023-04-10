"""Tests for the diagnostics data provided by the easyEnergy integration."""
from unittest.mock import MagicMock

from easyenergy import EasyEnergyNoDataError
import pytest

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2023-01-19 15:00:00")
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
            "title": "energy",
        },
        "energy_usage": {
            "current_hour_price": 0.22541,
            "next_hour_price": 0.24677,
            "average_price": 0.17665,
            "max_price": 0.24677,
            "min_price": 0.12308,
            "highest_price_time": "2023-01-19T16:00:00+00:00",
            "lowest_price_time": "2023-01-19T02:00:00+00:00",
            "percentage_of_max": 91.34,
        },
        "energy_return": {
            "current_hour_price": 0.18629,
            "next_hour_price": 0.20394,
            "average_price": 0.14599,
            "max_price": 0.20394,
            "min_price": 0.10172,
            "highest_price_time": "2023-01-19T16:00:00+00:00",
            "lowest_price_time": "2023-01-19T02:00:00+00:00",
            "percentage_of_max": 91.35,
        },
        "gas": {
            "current_hour_price": 0.7253,
            "next_hour_price": 0.7253,
        },
    }


@pytest.mark.freeze_time("2023-01-19 15:00:00")
async def test_diagnostics_no_gas_today(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_easyenergy: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics, no gas sensors available."""
    await async_setup_component(hass, "homeassistant", {})
    mock_easyenergy.gas_prices.side_effect = EasyEnergyNoDataError

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.easyenergy_today_gas_current_hour_price"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "entry": {
            "title": "energy",
        },
        "energy_usage": {
            "current_hour_price": 0.22541,
            "next_hour_price": 0.24677,
            "average_price": 0.17665,
            "max_price": 0.24677,
            "min_price": 0.12308,
            "highest_price_time": "2023-01-19T16:00:00+00:00",
            "lowest_price_time": "2023-01-19T02:00:00+00:00",
            "percentage_of_max": 91.34,
        },
        "energy_return": {
            "current_hour_price": 0.18629,
            "next_hour_price": 0.20394,
            "average_price": 0.14599,
            "max_price": 0.20394,
            "min_price": 0.10172,
            "highest_price_time": "2023-01-19T16:00:00+00:00",
            "lowest_price_time": "2023-01-19T02:00:00+00:00",
            "percentage_of_max": 91.35,
        },
        "gas": {
            "current_hour_price": None,
            "next_hour_price": None,
        },
    }
