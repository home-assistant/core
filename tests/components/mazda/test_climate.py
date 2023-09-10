"""The climate tests for the Mazda Connected Services integration."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.mazda.climate import (
    PRESET_DEFROSTER_FRONT,
    PRESET_DEFROSTER_FRONT_AND_REAR,
    PRESET_DEFROSTER_OFF,
    PRESET_DEFROSTER_REAR,
)
from homeassistant.components.mazda.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import init_integration

from tests.common import MockConfigEntry, load_fixture


async def test_climate_setup(hass: HomeAssistant) -> None:
    """Test the setup of the climate entity."""
    await init_integration(hass, electric_vehicle=True)

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("climate.my_mazda3_climate")
    assert entry
    assert entry.unique_id == "JM000000000000000"

    state = hass.states.get("climate.my_mazda3_climate")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Climate"


@pytest.mark.parametrize(
    (
        "region",
        "hvac_on",
        "target_temperature",
        "temperature_unit",
        "front_defroster",
        "rear_defroster",
        "current_temperature_celsius",
        "expected_hvac_mode",
        "expected_preset_mode",
        "expected_min_temp",
        "expected_max_temp",
    ),
    [
        # Test with HVAC off
        (
            "MNAO",
            False,
            20,
            "C",
            False,
            False,
            22,
            HVACMode.OFF,
            PRESET_DEFROSTER_OFF,
            15.5,
            28.5,
        ),
        # Test with HVAC on
        (
            "MNAO",
            True,
            20,
            "C",
            False,
            False,
            22,
            HVACMode.HEAT_COOL,
            PRESET_DEFROSTER_OFF,
            15.5,
            28.5,
        ),
        # Test with front defroster on
        (
            "MNAO",
            False,
            20,
            "C",
            True,
            False,
            22,
            HVACMode.OFF,
            PRESET_DEFROSTER_FRONT,
            15.5,
            28.5,
        ),
        # Test with rear defroster on
        (
            "MNAO",
            False,
            20,
            "C",
            False,
            True,
            22,
            HVACMode.OFF,
            PRESET_DEFROSTER_REAR,
            15.5,
            28.5,
        ),
        # Test with front and rear defrosters on
        (
            "MNAO",
            False,
            20,
            "C",
            True,
            True,
            22,
            HVACMode.OFF,
            PRESET_DEFROSTER_FRONT_AND_REAR,
            15.5,
            28.5,
        ),
        # Test with temperature unit F
        (
            "MNAO",
            False,
            70,
            "F",
            False,
            False,
            22,
            HVACMode.OFF,
            PRESET_DEFROSTER_OFF,
            61.0,
            83.0,
        ),
        # Test with Japan region (uses different min/max temp settings)
        (
            "MJO",
            False,
            20,
            "C",
            False,
            False,
            22,
            HVACMode.OFF,
            PRESET_DEFROSTER_OFF,
            18.5,
            31.5,
        ),
    ],
)
async def test_climate_state(
    hass: HomeAssistant,
    region,
    hvac_on,
    target_temperature,
    temperature_unit,
    front_defroster,
    rear_defroster,
    current_temperature_celsius,
    expected_hvac_mode,
    expected_preset_mode,
    expected_min_temp,
    expected_max_temp,
) -> None:
    """Test getting the state of the climate entity."""
    if temperature_unit == "F":
        hass.config.units = US_CUSTOMARY_SYSTEM

    get_vehicles_fixture = json.loads(load_fixture("mazda/get_vehicles.json"))
    get_vehicles_fixture[0]["isElectric"] = True
    get_vehicle_status_fixture = json.loads(
        load_fixture("mazda/get_vehicle_status.json")
    )
    get_ev_vehicle_status_fixture = json.loads(
        load_fixture("mazda/get_ev_vehicle_status.json")
    )
    get_ev_vehicle_status_fixture["hvacInfo"][
        "interiorTemperatureCelsius"
    ] = current_temperature_celsius
    get_hvac_setting_fixture = {
        "temperature": target_temperature,
        "temperatureUnit": temperature_unit,
        "frontDefroster": front_defroster,
        "rearDefroster": rear_defroster,
    }

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        return_value=True,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        return_value=get_vehicles_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicle_status",
        return_value=get_vehicle_status_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_ev_vehicle_status",
        return_value=get_ev_vehicle_status_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_assumed_hvac_mode",
        return_value=hvac_on,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_assumed_hvac_setting",
        return_value=get_hvac_setting_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_hvac_setting",
        return_value=get_hvac_setting_fixture,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_EMAIL: "example@example.com",
                CONF_PASSWORD: "password",
                CONF_REGION: region,
            },
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.my_mazda3_climate")
    assert state
    assert state.state == expected_hvac_mode
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Climate"
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    assert state.attributes.get(ATTR_HVAC_MODES) == [HVACMode.HEAT_COOL, HVACMode.OFF]
    assert state.attributes.get(ATTR_PRESET_MODES) == [
        PRESET_DEFROSTER_OFF,
        PRESET_DEFROSTER_FRONT,
        PRESET_DEFROSTER_REAR,
        PRESET_DEFROSTER_FRONT_AND_REAR,
    ]
    assert state.attributes.get(ATTR_MIN_TEMP) == expected_min_temp
    assert state.attributes.get(ATTR_MAX_TEMP) == expected_max_temp
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) == round(
        hass.config.units.temperature(
            current_temperature_celsius, UnitOfTemperature.CELSIUS
        )
    )
    assert state.attributes.get(ATTR_TEMPERATURE) == target_temperature
    assert state.attributes.get(ATTR_PRESET_MODE) == expected_preset_mode


@pytest.mark.parametrize(
    ("hvac_mode", "api_method"),
    [
        (HVACMode.HEAT_COOL, "turn_on_hvac"),
        (HVACMode.OFF, "turn_off_hvac"),
    ],
)
async def test_set_hvac_mode(hass: HomeAssistant, hvac_mode, api_method) -> None:
    """Test turning on and off the HVAC system."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.my_mazda3_climate", ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    await hass.async_block_till_done()

    getattr(client_mock, api_method).assert_called_once_with(12345)


async def test_set_target_temperature(hass: HomeAssistant) -> None:
    """Test setting the target temperature of the climate entity."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.my_mazda3_climate", ATTR_TEMPERATURE: 22},
        blocking=True,
    )
    await hass.async_block_till_done()

    client_mock.set_hvac_setting.assert_called_once_with(12345, 22, "C", True, False)


@pytest.mark.parametrize(
    ("preset_mode", "front_defroster", "rear_defroster"),
    [
        (PRESET_DEFROSTER_OFF, False, False),
        (PRESET_DEFROSTER_FRONT, True, False),
        (PRESET_DEFROSTER_REAR, False, True),
        (PRESET_DEFROSTER_FRONT_AND_REAR, True, True),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant, preset_mode, front_defroster, rear_defroster
) -> None:
    """Test turning on and off the front and rear defrosters."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.my_mazda3_climate",
            ATTR_PRESET_MODE: preset_mode,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    client_mock.set_hvac_setting.assert_called_once_with(
        12345, 20, "C", front_defroster, rear_defroster
    )
