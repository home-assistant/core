"""The climate tests for the Airzone Cloud platform."""
from unittest.mock import patch

from aioairzone_cloud.exceptions import AirzoneCloudError
import pytest

from homeassistant.components.airzone.const import API_TEMPERATURE_STEP
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .util import async_init_integration


async def test_airzone_create_climates(hass: HomeAssistant) -> None:
    """Test creation of climates."""

    await async_init_integration(hass)

    # Aidoos
    state = hass.states.get("climate.bron")
    assert state.state == HVACMode.OFF
    assert ATTR_CURRENT_HUMIDITY not in state.attributes
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.OFF,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 15
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == API_TEMPERATURE_STEP
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    state = hass.states.get("climate.bron_pro")
    assert state.state == HVACMode.COOL
    assert ATTR_CURRENT_HUMIDITY not in state.attributes
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.OFF,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 15
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == API_TEMPERATURE_STEP
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    # Groups
    state = hass.states.get("climate.group")
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 27
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.OFF,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 15
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == API_TEMPERATURE_STEP
    assert state.attributes[ATTR_TEMPERATURE] == 24.0

    # Installations
    state = hass.states.get("climate.house")
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 27
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.OFF,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 15
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == API_TEMPERATURE_STEP
    assert state.attributes[ATTR_TEMPERATURE] == 23.0

    # Zones
    state = hass.states.get("climate.dormitorio")
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 24
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.OFF,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 15
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == API_TEMPERATURE_STEP
    assert state.attributes[ATTR_TEMPERATURE] == 24.0

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 30
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.OFF,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 15
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == API_TEMPERATURE_STEP
    assert state.attributes[ATTR_TEMPERATURE] == 24.0


async def test_airzone_climate_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning on/off."""

    await async_init_integration(hass)

    # Aidoos
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "climate.bron",
            },
            blocking=True,
        )

    state = hass.states.get("climate.bron")
    assert state.state == HVACMode.HEAT

    # Groups
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_group",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "climate.group",
            },
            blocking=True,
        )

    state = hass.states.get("climate.group")
    assert state.state == HVACMode.COOL

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_group",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "climate.group",
            },
            blocking=True,
        )

    state = hass.states.get("climate.group")
    assert state.state == HVACMode.OFF

    # Installations
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_installation",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "climate.house",
            },
            blocking=True,
        )

    state = hass.states.get("climate.house")
    assert state.state == HVACMode.COOL

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_installation",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "climate.house",
            },
            blocking=True,
        )

    state = hass.states.get("climate.house")
    assert state.state == HVACMode.OFF

    # Zones
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "climate.dormitorio",
            },
            blocking=True,
        )

    state = hass.states.get("climate.dormitorio")
    assert state.state == HVACMode.COOL

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: "climate.salon",
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.OFF


async def test_airzone_climate_set_hvac_mode(hass: HomeAssistant) -> None:
    """Test setting the HVAC mode."""

    await async_init_integration(hass)

    # Aidoos
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.bron",
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            blocking=True,
        )

    state = hass.states.get("climate.bron")
    assert state.state == HVACMode.HEAT_COOL

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.bron",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get("climate.bron")
    assert state.state == HVACMode.OFF

    # Groups
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_group",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.group",
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )

    state = hass.states.get("climate.group")
    assert state.state == HVACMode.DRY

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_group",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.group",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get("climate.group")
    assert state.state == HVACMode.OFF

    # Installations
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_installation",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.house",
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )

    state = hass.states.get("climate.house")
    assert state.state == HVACMode.DRY

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_installation",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.house",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get("climate.house")
    assert state.state == HVACMode.OFF

    # Zones
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.HEAT

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.OFF


async def test_airzone_climate_set_hvac_slave_error(hass: HomeAssistant) -> None:
    """Test setting the HVAC mode for a slave zone."""

    await async_init_integration(hass)

    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.dormitorio",
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    state = hass.states.get("climate.dormitorio")
    assert state.state == HVACMode.COOL


async def test_airzone_climate_set_temp(hass: HomeAssistant) -> None:
    """Test setting the target temperature."""

    await async_init_integration(hass)

    # Groups
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_group",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.group",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.group")
    assert state.attributes[ATTR_TEMPERATURE] == 20.5

    # Installations
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_installation",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.house",
                ATTR_HVAC_MODE: HVACMode.HEAT,
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.house")
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 20.5

    # Zones
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        return_value=None,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_HVAC_MODE: HVACMode.HEAT,
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 20.5


async def test_airzone_climate_set_temp_error(hass: HomeAssistant) -> None:
    """Test error when setting the target temperature."""

    await async_init_integration(hass)

    # Aidoos
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        side_effect=AirzoneCloudError,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.bron",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.bron")
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    # Groups
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_group",
        side_effect=AirzoneCloudError,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.group",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.group")
    assert state.attributes[ATTR_TEMPERATURE] == 24.0

    # Installations
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_put_installation",
        side_effect=AirzoneCloudError,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.house",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.house")
    assert state.attributes[ATTR_TEMPERATURE] == 23.0

    # Zones
    with patch(
        "homeassistant.components.airzone_cloud.AirzoneCloudApi.api_patch_device",
        side_effect=AirzoneCloudError,
    ), pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.salon",
                ATTR_TEMPERATURE: 20.5,
            },
            blocking=True,
        )

    state = hass.states.get("climate.salon")
    assert state.attributes[ATTR_TEMPERATURE] == 24.0
