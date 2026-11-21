"""The tests for the group climate platform."""

from typing import Any

import pytest
from pytest_homeassistant.common import assert_setup_component
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityFeature,
    ClimateService,
    ClimateServiceArgument,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

CLIMATE_GROUP = "climate.climate_group"

HEATPUMP_ENTITY_ID = "climate.heatpump"
HVAC_ENTITY_ID = "climate.hvac"
ECOBEE_ENTITY_ID = "climate.ecobee"
DEMO_ENTITY_IDS = [HEATPUMP_ENTITY_ID, HVAC_ENTITY_ID, ECOBEE_ENTITY_ID]

MEMBER_ONE = "climate.member_one"
MEMBER_TWO = "climate.member_two"


async def _setup_group(
    hass: HomeAssistant, entity_ids: list[str], *, demo: bool = False
) -> None:
    """Set up a climate group, optionally together with the demo platform."""
    platforms: list[dict[str, Any]] = [
        {
            "platform": "group",
            CONF_ENTITIES: entity_ids,
            CONF_UNIQUE_ID: "unique_identifier",
        }
    ]
    if demo:
        platforms.insert(0, {"platform": "demo"})
    with assert_setup_component(len(platforms), CLIMATE_DOMAIN):
        await async_setup_component(hass, CLIMATE_DOMAIN, {CLIMATE_DOMAIN: platforms})
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def test_state_and_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the group state and attributes are combined from the demo members."""
    await _setup_group(hass, DEMO_ENTITY_IDS, demo=True)

    assert hass.states.get(CLIMATE_GROUP) == snapshot
    assert entity_registry.async_get(CLIMATE_GROUP).unique_id == "unique_identifier"


@pytest.mark.parametrize(
    ("member_states", "expected_state"),
    [
        pytest.param(
            [STATE_UNAVAILABLE, STATE_UNAVAILABLE], STATE_UNAVAILABLE, id="unavailable"
        ),
        pytest.param([STATE_UNKNOWN, STATE_UNAVAILABLE], STATE_UNKNOWN, id="unknown"),
        pytest.param(["off", "off"], "off", id="all_off"),
        pytest.param(["off", STATE_UNAVAILABLE], "off", id="off_and_unavailable"),
        pytest.param(["cool", "heat"], "heat", id="heat_over_cool"),
        pytest.param(["heat_cool", "cool"], "cool", id="cool_over_heat_cool"),
        pytest.param(["auto", "heat_cool"], "heat_cool", id="heat_cool_over_auto"),
        pytest.param(["dry", "auto"], "auto", id="auto_over_dry"),
        pytest.param(["fan_only", "dry"], "dry", id="dry_over_fan_only"),
        pytest.param(["off", "fan_only"], "fan_only", id="fan_only_over_off"),
        pytest.param([STATE_UNKNOWN, "cool"], "cool", id="cool_and_unknown"),
    ],
)
async def test_hvac_mode_priority(
    hass: HomeAssistant, member_states: list[str], expected_state: str
) -> None:
    """Test the group reports the member hvac mode with the highest priority."""
    await _setup_group(hass, [MEMBER_ONE, MEMBER_TWO])

    hass.states.async_set(MEMBER_ONE, member_states[0])
    hass.states.async_set(MEMBER_TWO, member_states[1])
    await hass.async_block_till_done()

    assert hass.states.get(CLIMATE_GROUP).state == expected_state


@pytest.mark.parametrize(
    ("member_actions", "expected_action"),
    [
        pytest.param(["cooling", "heating"], "heating", id="heating_over_cooling"),
        pytest.param(
            ["defrosting", "preheating"], "preheating", id="preheating_over_defrosting"
        ),
        pytest.param(
            ["cooling", "defrosting"], "defrosting", id="defrosting_over_cooling"
        ),
        pytest.param(["drying", "cooling"], "cooling", id="cooling_over_drying"),
        pytest.param(["fan", "drying"], "drying", id="drying_over_fan"),
        pytest.param(["idle", "fan"], "fan", id="fan_over_idle"),
        pytest.param(["off", "idle"], "idle", id="idle_over_off"),
        pytest.param(["off", None], "off", id="off_and_missing"),
    ],
)
async def test_hvac_action_priority(
    hass: HomeAssistant,
    member_actions: list[str | None],
    expected_action: str,
) -> None:
    """Test the group reports the member hvac action with the highest priority."""
    await _setup_group(hass, [MEMBER_ONE, MEMBER_TWO])

    hass.states.async_set(MEMBER_ONE, "heat", {"hvac_action": member_actions[0]})
    hass.states.async_set(MEMBER_TWO, "heat", {"hvac_action": member_actions[1]})
    await hass.async_block_till_done()

    assert hass.states.get(CLIMATE_GROUP).attributes["hvac_action"] == expected_action


async def test_hvac_action_missing(hass: HomeAssistant) -> None:
    """Test the group has no hvac action when no member reports one."""
    await _setup_group(hass, [MEMBER_ONE, MEMBER_TWO])

    hass.states.async_set(MEMBER_ONE, "heat")
    hass.states.async_set(MEMBER_TWO, "cool")
    await hass.async_block_till_done()

    assert "hvac_action" not in hass.states.get(CLIMATE_GROUP).attributes


async def test_combined_ranges(hass: HomeAssistant) -> None:
    """Test min and max values are the range all members accept."""
    await _setup_group(hass, [MEMBER_ONE, MEMBER_TWO])

    features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TARGET_HUMIDITY
    )
    hass.states.async_set(
        MEMBER_ONE,
        "heat",
        {
            ATTR_SUPPORTED_FEATURES: features,
            "temperature": 20,
            "min_temp": 5,
            "max_temp": 30,
            "target_temp_step": 0.5,
            "humidity": 40,
            "min_humidity": 30,
            "max_humidity": 80,
            "target_humidity_step": 1,
        },
    )
    hass.states.async_set(
        MEMBER_TWO,
        "heat",
        {
            ATTR_SUPPORTED_FEATURES: features,
            "temperature": 23,
            "min_temp": 10,
            "max_temp": 35,
            "target_temp_step": 1,
            "humidity": 50,
            "min_humidity": 20,
            "max_humidity": 70,
            "target_humidity_step": 5,
        },
    )
    await hass.async_block_till_done()

    attributes = hass.states.get(CLIMATE_GROUP).attributes
    assert attributes["temperature"] == 21.5
    assert attributes["min_temp"] == 10
    assert attributes["max_temp"] == 30
    assert attributes["target_temp_step"] == 1
    assert attributes["humidity"] == 45
    assert attributes["min_humidity"] == 30
    assert attributes["max_humidity"] == 70
    assert attributes["target_humidity_step"] == 5


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param(
            ClimateService.SET_TEMPERATURE,
            {ClimateServiceArgument.TEMPERATURE: 25},
            id="set_temperature",
        ),
        pytest.param(
            ClimateService.SET_TEMPERATURE,
            {
                ClimateServiceArgument.TARGET_TEMP_LOW: 18,
                ClimateServiceArgument.TARGET_TEMP_HIGH: 26,
            },
            id="set_temperature_range",
        ),
        pytest.param(
            ClimateService.SET_TEMPERATURE,
            {
                ClimateServiceArgument.TEMPERATURE: 25,
                ClimateServiceArgument.HVAC_MODE: "cool",
            },
            id="set_temperature_with_hvac_mode",
        ),
        pytest.param(
            ClimateService.SET_HUMIDITY,
            {ClimateServiceArgument.HUMIDITY: 60},
            id="set_humidity",
        ),
        pytest.param(
            ClimateService.SET_HVAC_MODE,
            {ClimateServiceArgument.HVAC_MODE: "heat"},
            id="set_hvac_mode",
        ),
        pytest.param(
            ClimateService.SET_FAN_MODE,
            {ClimateServiceArgument.FAN_MODE: "on_high"},
            id="set_fan_mode",
        ),
        pytest.param(
            ClimateService.SET_PRESET_MODE,
            {ClimateServiceArgument.PRESET_MODE: "away"},
            id="set_preset_mode",
        ),
        pytest.param(
            ClimateService.SET_SWING_MODE,
            {ClimateServiceArgument.SWING_MODE: "1"},
            id="set_swing_mode",
        ),
        pytest.param(
            ClimateService.SET_SWING_HORIZONTAL_MODE,
            {ClimateServiceArgument.SWING_HORIZONTAL_MODE: "rangefull"},
            id="set_swing_horizontal_mode",
        ),
        pytest.param(SERVICE_TURN_OFF, {}, id="turn_off"),
    ],
)
async def test_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service calls are only forwarded to members supporting them."""
    await _setup_group(hass, DEMO_ENTITY_IDS, demo=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: CLIMATE_GROUP, **service_data},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert [
        hass.states.get(entity_id) for entity_id in (*DEMO_ENTITY_IDS, CLIMATE_GROUP)
    ] == snapshot


async def test_turn_on_only_off_members(hass: HomeAssistant) -> None:
    """Test turn on leaves members which are already on in their mode."""
    await _setup_group(hass, DEMO_ENTITY_IDS, demo=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_HVAC_MODE,
        {ATTR_ENTITY_ID: HEATPUMP_ENTITY_ID, ClimateServiceArgument.HVAC_MODE: "off"},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: CLIMATE_GROUP},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(HEATPUMP_ENTITY_ID).state == "heat"
    assert hass.states.get(HVAC_ENTITY_ID).state == "cool"
    assert hass.states.get(ECOBEE_ENTITY_ID).state == "heat_cool"


async def test_set_mode_with_member_without_mode_list(hass: HomeAssistant) -> None:
    """Test setting a mode skips a member reporting no list for that mode."""
    await _setup_group(hass, [HVAC_ENTITY_ID, MEMBER_ONE], demo=True)

    hass.states.async_set(
        MEMBER_ONE,
        "heat",
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.FAN_MODE,
            "fan_modes": None,
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        ClimateService.SET_FAN_MODE,
        {ATTR_ENTITY_ID: CLIMATE_GROUP, ClimateServiceArgument.FAN_MODE: "on_low"},
        blocking=True,
    )

    assert hass.states.get(HVAC_ENTITY_ID).attributes["fan_mode"] == "on_low"
