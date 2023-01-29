"""Tests for the diagnostics data provided by the EnergyZero integration."""
from unittest.mock import MagicMock

from aiohttp import ClientSession
from energyzero import EnergyZeroNoDataError
import pytest

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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


@pytest.mark.freeze_time("2022-12-07 15:00:00")
async def test_diagnostics_no_gas_today(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_energyzero: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics, no gas sensors available."""
    await async_setup_component(hass, "homeassistant", {})
    mock_energyzero.gas_prices.side_effect = EnergyZeroNoDataError

    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.energyzero_today_gas_current_hour_price"]},
        blocking=True,
    )
    await hass.async_block_till_done()

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
            "current_hour_price": None,
            "next_hour_price": None,
        },
    }
