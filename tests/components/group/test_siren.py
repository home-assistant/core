"""The tests for the Group Siren platform."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_default_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test siren group default state."""
    hass.states.async_set("siren.alarm", "on")
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["siren.alarm", "siren.doorbell"],
                "name": "Alarm Group",
                "unique_id": "unique_identifier",
                "all": "false",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("siren.alarm_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == ["siren.alarm", "siren.doorbell"]

    entry = entity_registry.async_get("siren.alarm_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test the state reporting in 'any' mode for sirens."""
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["siren.test1", "siren.test2"],
                "all": "false",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("siren.siren_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("siren.test1", STATE_UNAVAILABLE)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNAVAILABLE

    # All group members unknown -> unknown
    hass.states.async_set("siren.test1", STATE_UNKNOWN)
    hass.states.async_set("siren.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    # Group members unknown or unavailable -> unknown
    hass.states.async_set("siren.test1", STATE_UNKNOWN)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    # At least one member on -> group on
    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_ON

    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_ON

    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_ON

    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_ON

    # Otherwise -> off
    hass.states.async_set("siren.test1", STATE_OFF)
    hass.states.async_set("siren.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_OFF

    hass.states.async_set("siren.test1", STATE_UNKNOWN)
    hass.states.async_set("siren.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_OFF

    hass.states.async_set("siren.test1", STATE_UNAVAILABLE)
    hass.states.async_set("siren.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_OFF

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("siren.test1")
    hass.states.async_remove("siren.test2")
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNAVAILABLE


async def test_state_reporting_all(hass: HomeAssistant) -> None:
    """Test the state reporting in 'all' mode for sirens."""
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["siren.test1", "siren.test2"],
                "all": "true",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("siren.siren_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("siren.test1", STATE_UNAVAILABLE)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNAVAILABLE

    # At least one member unknown or unavailable -> group unknown
    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    hass.states.async_set("siren.test1", STATE_UNKNOWN)
    hass.states.async_set("siren.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    hass.states.async_set("siren.test1", STATE_OFF)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    hass.states.async_set("siren.test1", STATE_OFF)
    hass.states.async_set("siren.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    hass.states.async_set("siren.test1", STATE_UNKNOWN)
    hass.states.async_set("siren.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNKNOWN

    # At least one member off -> group off
    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_OFF

    hass.states.async_set("siren.test1", STATE_OFF)
    hass.states.async_set("siren.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_OFF

    # Otherwise -> on
    hass.states.async_set("siren.test1", STATE_ON)
    hass.states.async_set("siren.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_ON

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("siren.test1")
    hass.states.async_remove("siren.test2")
    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_service_calls(hass: HomeAssistant) -> None:
    """Test service calls for sirens."""
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["siren.siren", "siren.siren_with_all_features"],
                    "all": "false",
                },
            ]
        },
    )

    await hass.async_block_till_done()

    group_state = hass.states.get("siren.siren_group")
    assert group_state.state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "siren.siren_group"},
        blocking=True,
    )
    assert hass.states.get("siren.siren").state == STATE_ON
    assert hass.states.get("siren.siren_with_all_features").state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "siren.siren_group"},
        blocking=True,
    )
    assert hass.states.get("siren.siren").state == STATE_OFF
    assert hass.states.get("siren.siren_with_all_features").state == STATE_OFF


async def test_reload(hass: HomeAssistant) -> None:
    """Test the ability to reload sirens."""
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "siren.siren",
                        "siren.siren_with_all_features",
                    ],
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("siren.siren_group").state == STATE_ON

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("siren.siren_group") is None
    assert hass.states.get("siren.master_siren_group") is not None


async def test_reload_with_platform_not_setup(hass: HomeAssistant) -> None:
    """Test the ability to reload sirens."""
    hass.states.async_set("siren.something", STATE_ON)
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: [
                {"platform": "demo"},
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "siren.something", "icon": "mdi:work"},
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

    assert hass.states.get("siren.siren_group") is None
    assert hass.states.get("siren.master_siren_group") is not None


async def test_reload_with_base_integration_platform_not_setup(
    hass: HomeAssistant,
) -> None:
    """Test the ability to reload sirens."""
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "siren.something", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("siren.siren", STATE_ON)
    hass.states.async_set("siren.siren_with_all_features", STATE_OFF)

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("siren.siren_group") is None
    assert hass.states.get("siren.master_siren_group") is not None
    assert hass.states.get("siren.master_siren_group").state == STATE_ON


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested siren group."""
    await async_setup_component(
        hass,
        SIREN_DOMAIN,
        {
            SIREN_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["siren.some_group"],
                    "name": "Nested Group",
                    "all": "false",
                },
                {
                    "platform": DOMAIN,
                    "entities": ["siren.siren", "siren.siren_with_all_features"],
                    "name": "Some Group",
                    "all": "false",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("siren.some_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "siren.siren",
        "siren.siren_with_all_features",
    ]

    state = hass.states.get("siren.nested_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == ["siren.some_group"]

    # Test controlling the nested group
    async with asyncio.timeout(0.5):
        await hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "siren.nested_group"},
            blocking=True,
        )
    assert hass.states.get("siren.siren").state == STATE_OFF
    assert hass.states.get("siren.siren_with_all_features").state == STATE_OFF
    assert hass.states.get("siren.some_group").state == STATE_OFF
    assert hass.states.get("siren.nested_group").state == STATE_OFF
