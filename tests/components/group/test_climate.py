"""The tests for the Group Climate platform."""
from unittest.mock import patch

import async_timeout

from homeassistant import config as hass_config
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
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
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_default_state(hass):
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
    assert state.attributes.get(ATTR_HVAC_MODES) == [HVACMode.OFF]

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("climate.bedroom_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting(hass):
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


async def test_supported_features(hass):
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

    hass.states.async_set("climate.test1", HVACMode.AUTO, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    state = hass.states.get("climate.climate_group")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0

    hass.states.async_set(
        "climate.test2",
        HVACMode.AUTO,
        {ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.SWING_MODE},
    )
    await hass.async_block_till_done()
    state = hass.states.get("climate.climate_group")
    # test1: 0, test2: SWING_MODE
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == ClimateEntityFeature.SWING_MODE

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
    # test1: PRESET_MODE | SWING_MODE, test2: SWING_MODE
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.SWING_MODE
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
        == ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.SWING_MODE
    )


async def test_reload(hass):
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


async def test_reload_with_platform_not_setup(hass):
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


async def test_reload_with_base_integration_platform_not_setup(hass):
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


async def test_nested_group(hass):
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

    state = hass.states.get("climate.bedroom_group")
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "climate.hvac",
        "climate.ecobee",
    ]

    state = hass.states.get("climate.nested_group")
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes.get(ATTR_ENTITY_ID) == ["climate.bedroom_group"]

    # Test controlling the nested group
    async with async_timeout.timeout(0.5):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "climate.nested_group"},
            blocking=True,
        )
    assert hass.states.get("climate.ecobee").state == HVACMode.OFF
    assert hass.states.get("climate.hvac").state == HVACMode.OFF
    assert hass.states.get("climate.bedroom_group").state == HVACMode.OFF
    assert hass.states.get("climate.nested_group").state == HVACMode.OFF
