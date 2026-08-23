"""Tests for the Atag water heater platform."""

from unittest.mock import patch

from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import UID, init_integration

from tests.test_util.aiohttp import AiohttpClientMocker

WATER_HEATER_ID = "water_heater.atag_thermostat_atag"


async def test_water_heater(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation of Atag water heater."""
    with patch("pyatag.entities.DHW.status"):
        entry = await init_integration(hass, aioclient_mock)

        assert entity_registry.async_is_registered(WATER_HEATER_ID)
        entry = entity_registry.async_get(WATER_HEATER_ID)
        assert entry.unique_id == f"{UID}-water_heater"


async def test_setting_target_temperature(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setting the water heater device."""
    await init_integration(hass, aioclient_mock)
    with patch("pyatag.entities.DHW.set_temp") as mock_set_temp:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: WATER_HEATER_ID, ATTR_TEMPERATURE: 50},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_temp.assert_called_once_with(50)
