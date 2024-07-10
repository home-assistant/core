"""Tests for the Atag climate platform."""

from unittest.mock import PropertyMock, patch

from homeassistant.components.atag.climate import DOMAIN, PRESET_MAP
from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import UID, init_integration

from tests.test_util.aiohttp import AiohttpClientMocker

CLIMATE_ID = f"{Platform.CLIMATE}.{DOMAIN}"


async def test_climate(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the creation and values of Atag climate device."""
    await init_integration(hass, aioclient_mock)

    assert entity_registry.async_is_registered(CLIMATE_ID)
    entity = entity_registry.async_get(CLIMATE_ID)
    assert entity.unique_id == f"{UID}-{Platform.CLIMATE}"
    assert hass.states.get(CLIMATE_ID).attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_setting_climate(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setting the climate device."""
    await init_integration(hass, aioclient_mock)
    with patch("pyatag.entities.Climate.set_temp") as mock_set_temp:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: CLIMATE_ID, ATTR_TEMPERATURE: 15},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_temp.assert_called_once_with(15)

    with patch("pyatag.entities.Climate.set_preset_mode") as mock_set_preset:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: CLIMATE_ID, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_preset.assert_called_once_with(PRESET_MAP[PRESET_AWAY])

    with patch("pyatag.entities.Climate.set_hvac_mode") as mock_set_hvac:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: CLIMATE_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_hvac.assert_called_once_with(HVACMode.HEAT)


async def test_incorrect_modes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test incorrect values are handled correctly."""
    with patch(
        "pyatag.entities.Climate.hvac_mode",
        new_callable=PropertyMock(return_value="bug"),
    ):
        await init_integration(hass, aioclient_mock)
        assert hass.states.get(CLIMATE_ID).state == STATE_UNKNOWN


async def test_update_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test data is not destroyed on update failure."""
    entry = await init_integration(hass, aioclient_mock)
    await async_setup_component(hass, HA_DOMAIN, {})
    assert hass.states.get(CLIMATE_ID).state == HVACMode.HEAT
    coordinator = hass.data[DOMAIN][entry.entry_id]
    with patch("pyatag.AtagOne.update", side_effect=TimeoutError) as updater:
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        updater.assert_called_once()
        assert not coordinator.last_update_success
        assert coordinator.data.id == UID
