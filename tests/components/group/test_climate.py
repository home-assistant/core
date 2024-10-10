"""The tests for the Group Climate platform."""

from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_SWING_MODES,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_default_state(hass: HomeAssistant) -> None:
    """Test component group default state."""
    hass.states.async_set("climate.kitchen", HVACMode.AUTO)
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["climate.kitchen", "climate.bedroom"],
                "name": "Bedroom Group",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("climate.bedroom_group")
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "climate.kitchen",
        "climate.bedroom",
    ]
    assert state.attributes.get(ATTR_SWING_MODES) is None
    assert state.attributes.get(ATTR_FAN_MODES) is None
    assert state.attributes.get(ATTR_HVAC_MODES) == []

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("climate.bedroom_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test the state reporting.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if all group members are unknown.
    Otherwise, the group state is on if at least one group member is on.
    Otherwise, the group state is off.
    """
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["climate.test1", "climate.test2"],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("climate.climate_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("climate.test1", STATE_UNAVAILABLE)
    hass.states.async_set("climate.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == STATE_UNAVAILABLE

    # All group members unknown -> unknown
    hass.states.async_set("climate.test1", STATE_UNKNOWN)
    hass.states.async_set("climate.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == STATE_UNKNOWN

    # Group members unknown or unavailable -> unknown
    hass.states.async_set("climate.test1", STATE_UNKNOWN)
    hass.states.async_set("climate.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == STATE_UNKNOWN

    # At least one member on -> group on
    hass.states.async_set("climate.test1", HVACMode.AUTO)
    hass.states.async_set("climate.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.AUTO

    hass.states.async_set("climate.test1", HVACMode.AUTO)
    hass.states.async_set("climate.test2", HVACMode.OFF)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.AUTO

    hass.states.async_set("climate.test1", HVACMode.AUTO)
    hass.states.async_set("climate.test2", HVACMode.AUTO)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.AUTO

    hass.states.async_set("climate.test1", HVACMode.AUTO)
    hass.states.async_set("climate.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.AUTO

    # Otherwise -> off
    hass.states.async_set("climate.test1", HVACMode.OFF)
    hass.states.async_set("climate.test2", HVACMode.OFF)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.OFF

    hass.states.async_set("climate.test1", STATE_UNKNOWN)
    hass.states.async_set("climate.test2", HVACMode.OFF)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.OFF

    hass.states.async_set("climate.test1", STATE_UNAVAILABLE)
    hass.states.async_set("climate.test2", HVACMode.OFF)
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.OFF

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("climate.test1")
    hass.states.async_remove("climate.test2")
    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == STATE_UNAVAILABLE


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test supported features reporting."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["climate.test1", "climate.test2"],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set(
        "climate.test1",
        HVACMode.AUTO,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE,
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.climate_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    hass.states.async_set(
        "climate.test2",
        HVACMode.AUTO,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.SWING_MODE,
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.climate_group")
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )

    hass.states.async_set(
        "climate.test1",
        HVACMode.AUTO,
        {
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.SWING_MODE
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.climate_group")
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )

    # Test that unknown feature 256 is blocked
    hass.states.async_set(
        "climate.test2", HVACMode.AUTO, {ATTR_SUPPORTED_FEATURES: 256}
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.climate_group")

    # test1: PRESET_MODE | SWING_MODE, test2: 256
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
    )


async def test_reload(hass: HomeAssistant) -> None:
    """Test the ability to reload lights."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "climate.hvac",
                        "climate.ecobee",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("climate.climate_group").state == HVACMode.COOL

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("climate.climate_group") is None
    assert hass.states.get("climate.upstairs_g") is not None
    assert hass.states.get("climate.downstairs_g") is not None


async def test_reload_with_platform_not_setup(hass: HomeAssistant) -> None:
    """Test the ability to reload climate."""
    hass.states.async_set("climate.bowl", HVACMode.AUTO)
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "climate.Bowl", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("climate.climate_group") is None
    assert hass.states.get("climate.upstairs_g") is not None
    assert hass.states.get("climate.downstairs_g") is not None


async def test_reload_with_base_integration_platform_not_setup(
    hass: HomeAssistant,
) -> None:
    """Test the ability to reload climate."""
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "climate.Bowl", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("climate.upstairs", HVACMode.AUTO)
    hass.states.async_set("climate.upstairs_2", HVACMode.AUTO)

    hass.states.async_set("climate.downstairs", HVACMode.OFF)
    hass.states.async_set("climate.downstairs_2", HVACMode.OFF)

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("climate.climate_group") is None
    assert hass.states.get("climate.upstairs_g") is not None
    assert hass.states.get("climate.downstairs_g") is not None
    assert hass.states.get("climate.upstairs_g").state == HVACMode.AUTO
    assert hass.states.get("climate.downstairs_g").state == HVACMode.OFF


async def test_set_temperature(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["climate.hvac", "climate.ecobee"],
                    "name": "Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("climate.hvac").state == HVACMode.COOL
    assert hass.states.get("climate.ecobee").state == HVACMode.HEAT_COOL
    assert hass.states.get("climate.group").state == HVACMode.COOL
    assert hass.states.get("climate.ecobee").attributes.get(ATTR_TEMPERATURE) is None
    assert hass.states.get("climate.hvac").attributes.get(ATTR_TEMPERATURE) == 21.0
    assert hass.states.get("climate.group").attributes.get(ATTR_TEMPERATURE) == 21.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.group",
            ATTR_TEMPERATURE: 23.0,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Ecobee does not support setting a target temperature.
    assert hass.states.get("climate.ecobee").attributes.get(ATTR_TEMPERATURE) is None
    assert (
        hass.states.get("climate.ecobee").attributes.get(ATTR_TARGET_TEMP_LOW) == 23.0
    )
    assert (
        hass.states.get("climate.ecobee").attributes.get(ATTR_TARGET_TEMP_HIGH) == 23.0
    )
    assert hass.states.get("climate.hvac").attributes.get(ATTR_TEMPERATURE) == 23.0
    assert hass.states.get("climate.group").attributes.get(ATTR_TEMPERATURE) == 23.0
    assert hass.states.get("climate.hvac").state == HVACMode.HEAT
    assert hass.states.get("climate.ecobee").state == HVACMode.HEAT
    assert hass.states.get("climate.group").state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.group",
            ATTR_TARGET_TEMP_LOW: 21.0,
            ATTR_TARGET_TEMP_HIGH: 24.0,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Ecobee does not support setting a target temperature.
    assert (
        hass.states.get("climate.ecobee").attributes.get(ATTR_TARGET_TEMP_LOW) == 21.0
    )
    assert (
        hass.states.get("climate.ecobee").attributes.get(ATTR_TARGET_TEMP_HIGH) == 24.0
    )
    assert hass.states.get("climate.hvac").attributes.get(ATTR_TEMPERATURE) == 22.5
    assert hass.states.get("climate.group").attributes.get(ATTR_TEMPERATURE) == 22.5
    assert hass.states.get("climate.group").attributes.get(ATTR_TARGET_TEMP_LOW) == 21.0
    assert (
        hass.states.get("climate.group").attributes.get(ATTR_TARGET_TEMP_HIGH) == 24.0
    )


async def test_set_humidity(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["climate.hvac", "climate.ecobee"],
                    "name": "Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_HUMIDITY) is None
    assert hass.states.get("climate.hvac").attributes.get(ATTR_HUMIDITY) == 67.4
    assert hass.states.get("climate.group").attributes.get(ATTR_HUMIDITY) == 67.4

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: "climate.group",
            ATTR_HUMIDITY: 55,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Ecobee does not support setting a target humidity.
    assert hass.states.get("climate.ecobee").attributes.get(ATTR_HUMIDITY) is None
    assert hass.states.get("climate.hvac").attributes.get(ATTR_HUMIDITY) == 55
    assert hass.states.get("climate.group").attributes.get(ATTR_HUMIDITY) == 55


async def test_set_fan_mode(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["climate.hvac", "climate.ecobee"],
                    "name": "Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_FAN_MODE) == "auto_low"
    assert hass.states.get("climate.hvac").attributes.get(ATTR_FAN_MODE) == "on_high"
    assert hass.states.get("climate.group").attributes.get(ATTR_FAN_MODE) in (
        "on_high",
        "auto_low",
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: "climate.group",
            ATTR_FAN_MODE: "off",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_FAN_MODE) == "off"
    assert hass.states.get("climate.hvac").attributes.get(ATTR_FAN_MODE) == "off"
    assert hass.states.get("climate.group").attributes.get(ATTR_FAN_MODE) == "off"


async def test_set_swing_mode(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["climate.hvac", "climate.ecobee"],
                    "name": "Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_SWING_MODE) == "auto"
    assert hass.states.get("climate.hvac").attributes.get(ATTR_SWING_MODE) == "off"
    assert hass.states.get("climate.group").attributes.get(ATTR_SWING_MODE) in (
        "auto",
        "off",
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            ATTR_ENTITY_ID: "climate.group",
            ATTR_SWING_MODE: "auto",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_SWING_MODE) == "auto"
    assert hass.states.get("climate.hvac").attributes.get(ATTR_SWING_MODE) == "auto"
    assert hass.states.get("climate.group").attributes.get(ATTR_SWING_MODE) == "auto"


async def test_set_preset_mode(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["climate.hvac", "climate.ecobee"],
                    "name": "Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_PRESET_MODE) == "home"
    assert hass.states.get("climate.hvac").attributes.get(ATTR_PRESET_MODE) is None
    assert hass.states.get("climate.group").attributes.get(ATTR_PRESET_MODE) == "home"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.group",
            ATTR_PRESET_MODE: "away",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("climate.ecobee").attributes.get(ATTR_PRESET_MODE) == "away"
    assert hass.states.get("climate.hvac").attributes.get(ATTR_PRESET_MODE) is None
    assert hass.states.get("climate.group").attributes.get(ATTR_PRESET_MODE) == "away"


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested light group."""
    await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            CLIMATE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["climate.bedroom_group"],
                    "name": "Nested Group",
                },
                {
                    "platform": DOMAIN,
                    "entities": ["climate.hvac", "climate.ecobee"],
                    "name": "Bedroom Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state_hvac = hass.states.get("climate.hvac")
    assert state_hvac.state == HVACMode.COOL
    state_ecobee = hass.states.get("climate.ecobee")
    assert state_ecobee.state == HVACMode.HEAT_COOL
    state_group = hass.states.get("climate.bedroom_group")
    assert state_group is not None
    assert state_group.state == HVACMode.COOL
    assert state_group.attributes.get(ATTR_ENTITY_ID) == [
        "climate.hvac",
        "climate.ecobee",
    ]

    state_nested = hass.states.get("climate.nested_group")
    assert state_nested is not None
    assert state_nested.state == HVACMode.COOL
    assert state_nested.attributes.get(ATTR_ENTITY_ID) == ["climate.bedroom_group"]

    # Test controlling the nested group
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.nested_group", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("climate.ecobee").state == HVACMode.OFF
    assert hass.states.get("climate.hvac").state == HVACMode.OFF
    assert hass.states.get("climate.bedroom_group").state == HVACMode.OFF
    assert hass.states.get("climate.nested_group").state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.nested_group",
            ATTR_TEMPERATURE: 21.0,
        },
        blocking=True,
    )
    # Ecobee does not support setting a target temperature.
    assert hass.states.get("climate.ecobee").attributes.get(ATTR_TEMPERATURE) is None
    assert hass.states.get("climate.hvac").attributes.get(ATTR_TEMPERATURE) == 21.0
    assert (
        hass.states.get("climate.bedroom_group").attributes.get(ATTR_TEMPERATURE)
        == 21.0
    )
    assert (
        hass.states.get("climate.nested_group").attributes.get(ATTR_TEMPERATURE) == 21.0
    )
