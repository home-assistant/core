"""Test for fibaro climate entity."""
from unittest.mock import patch

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

ENTITY_ID = "climate.wohnen_romtermostat_168"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, {CLIMATE_DOMAIN})
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry.unique_id == "hc2_111111.168"


async def test_climate_attributes(hass: HomeAssistant) -> None:
    """Tests that the device attributes are correctly calculated."""
    await setup_platform(hass, {CLIMATE_DOMAIN})

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.OFF
    hvac_modes = state.attributes[ATTR_HVAC_MODES]
    hvac_modes.sort()
    assert hvac_modes == [HVACMode.HEAT, HVACMode.OFF]
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.attributes[ATTR_PRESET_MODES] == []
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )


async def test_set_hvac_mode_heat(hass: HomeAssistant) -> None:
    """Test that the hvac mode can be set."""
    await setup_platform(hass, {CLIMATE_DOMAIN})

    with patch("fiblary3.client.v4.devices.Controller.action") as mock_switch_on:
        assert await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_switch_on.assert_called_once()


async def test_set_target_temperature(hass: HomeAssistant) -> None:
    """Test that the climate target temperature can be set."""
    await setup_platform(hass, {CLIMATE_DOMAIN})

    with patch("fiblary3.client.v4.devices.Controller.action") as mock_switch_on:
        assert await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_switch_on.assert_called_once()
