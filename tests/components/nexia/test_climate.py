"""Tests for the nexia climate platform."""

from typing import Any
from unittest.mock import call

from nexia.const import HOLD_PERMANENT, OPERATION_MODE_COOL
from nexia.home import NexiaHome
import pytest

from homeassistant.components.climate import ATTR_HVAC_MODE, HVACMode
from homeassistant.components.nexia.const import ATTR_RUN_MODE, DOMAIN
from homeassistant.components.nexia.services import SERVICE_SET_HVAC_RUN_MODE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

ENTITY_ID = "climate.nick_office_nick_office"


async def test_climate_zones(hass: HomeAssistant, patch_nexia_home: NexiaHome) -> None:
    """Test creation climate zones."""

    await setup_integration(hass, patch_nexia_home)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "current_humidity": 52.0,
        "current_temperature": 22.8,
        "dehumidify_setpoint": 45.0,
        "fan_mode": "Auto",
        "fan_modes": ["Auto", "On", "Circulate"],
        "friendly_name": "Nick Office",
        "humidity": 45.0,
        "hvac_action": "cooling",
        "hvac_modes": ["off", "auto", "heat_cool", "heat", "cool"],
        "max_humidity": 65.0,
        "max_temp": 37.2,
        "min_humidity": 35.0,
        "min_temp": 12.8,
        "preset_mode": "None",
        "preset_modes": ["None", "Home", "Away", "Sleep"],
        "supported_features": 415,
        "target_temp_high": 26.1,
        "target_temp_low": 17.2,
        "target_temp_step": 1.0,
        "temperature": None,
    }
    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value, f"key = {key}"

    state = hass.states.get("climate.kitchen_kitchen")
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL

    expected_attributes = {
        "attribution": "Data provided by Trane Technologies",
        "current_humidity": 36.0,
        "current_temperature": 25.0,
        "dehumidify_setpoint": 50.0,
        "fan_mode": "Auto",
        "fan_modes": ["Auto", "On", "Circulate"],
        "friendly_name": "Kitchen",
        "humidity": 50.0,
        "hvac_action": "idle",
        "hvac_modes": ["off", "auto", "heat_cool", "heat", "cool"],
        "max_humidity": 65.0,
        "max_temp": 37.2,
        "min_humidity": 35.0,
        "min_temp": 12.8,
        "preset_mode": "None",
        "preset_modes": ["None", "Home", "Away", "Sleep"],
        "supported_features": 415,
        "target_temp_high": 26.1,
        "target_temp_low": 17.2,
        "target_temp_step": 1.0,
        "temperature": None,
    }

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    for key, value in expected_attributes.items():
        assert state.attributes[key] == value, f"key = {key}"


@pytest.mark.parametrize(
    ("service_data", "expected_hold_calls", "expected_set_mode_calls"),
    [
        pytest.param({ATTR_RUN_MODE: HOLD_PERMANENT}, 1, [], id="run_mode_only"),
        pytest.param(
            {ATTR_HVAC_MODE: HVACMode.COOL},
            0,
            [call(mode=OPERATION_MODE_COOL)],
            id="hvac_mode_only",
        ),
        pytest.param(
            {ATTR_RUN_MODE: HOLD_PERMANENT, ATTR_HVAC_MODE: HVACMode.COOL},
            1,
            [call(mode=OPERATION_MODE_COOL)],
            id="both",
        ),
    ],
)
async def test_set_hvac_run_mode(
    hass: HomeAssistant,
    patch_nexia_home: NexiaHome,
    service_data: dict[str, Any],
    expected_hold_calls: int,
    expected_set_mode_calls: list[Any],
) -> None:
    """Test the set_hvac_run_mode action with either field left out."""
    await setup_integration(hass, patch_nexia_home)
    zone = patch_nexia_home.get_thermostat_by_id(2000000).get_zone_by_id(100)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_RUN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert zone.set_permanent_hold.call_count == expected_hold_calls
    assert zone.set_mode.call_args_list == expected_set_mode_calls
