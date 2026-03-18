"""The tests for the Group Lock platform."""

from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.demo import lock as demo_lock
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_default_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test lock group default state."""
    hass.states.async_set("lock.front", "locked")
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["lock.front", "lock.back"],
                "name": "Door Group",
                "unique_id": "unique_identifier",
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("lock.door_group")
    assert state is not None
    assert state.state == LockState.LOCKED
    assert state.attributes.get(ATTR_ENTITY_ID) == ["lock.front", "lock.back"]

    entry = entity_registry.async_get("lock.door_group")
    assert entry
    assert entry.unique_id == "unique_identifier"


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test the state reporting.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if at least one group member is unknown or unavailable.
    Otherwise, the group state is jammed if at least one group member is jammed.
    Otherwise, the group state is locking if at least one group member is locking.
    Otherwise, the group state is unlocking if at least one group member is unlocking.
    Otherwise, the group state is unlocked if at least one group member is unlocked.
    Otherwise, the group state is locked.
    """
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: {
                "platform": DOMAIN,
                "entities": ["lock.test1", "lock.test2"],
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Initial state with no group member in the state machine -> unavailable
    assert hass.states.get("lock.lock_group").state == STATE_UNAVAILABLE

    # All group members unavailable -> unavailable
    hass.states.async_set("lock.test1", STATE_UNAVAILABLE)
    hass.states.async_set("lock.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("lock.lock_group").state == STATE_UNAVAILABLE

    # The group state is unknown if all group members are unknown or unavailable.
    for state_1 in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        hass.states.async_set("lock.test1", state_1)
        hass.states.async_set("lock.test2", STATE_UNKNOWN)
        await hass.async_block_till_done()
        assert hass.states.get("lock.lock_group").state == STATE_UNKNOWN

    # At least one member jammed -> group jammed
    for state_1 in (
        LockState.JAMMED,
        LockState.LOCKED,
        LockState.LOCKING,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
        LockState.UNLOCKED,
        LockState.UNLOCKING,
    ):
        hass.states.async_set("lock.test1", state_1)
        hass.states.async_set("lock.test2", LockState.JAMMED)
        await hass.async_block_till_done()
        assert hass.states.get("lock.lock_group").state == LockState.JAMMED

    # At least one member locking -> group unlocking
    for state_1 in (
        LockState.LOCKED,
        LockState.LOCKING,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
        LockState.UNLOCKED,
        LockState.UNLOCKING,
    ):
        hass.states.async_set("lock.test1", state_1)
        hass.states.async_set("lock.test2", LockState.LOCKING)
        await hass.async_block_till_done()
        assert hass.states.get("lock.lock_group").state == LockState.LOCKING

    # At least one member unlocking -> group unlocking
    for state_1 in (
        LockState.LOCKED,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
        LockState.UNLOCKED,
        LockState.UNLOCKING,
    ):
        hass.states.async_set("lock.test1", state_1)
        hass.states.async_set("lock.test2", LockState.UNLOCKING)
        await hass.async_block_till_done()
        assert hass.states.get("lock.lock_group").state == LockState.UNLOCKING

    # At least one member unlocked -> group unlocked
    for state_1 in (
        LockState.LOCKED,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
        LockState.UNLOCKED,
    ):
        hass.states.async_set("lock.test1", state_1)
        hass.states.async_set("lock.test2", LockState.UNLOCKED)
        await hass.async_block_till_done()
        assert hass.states.get("lock.lock_group").state == LockState.UNLOCKED

    # Otherwise -> locked
    hass.states.async_set("lock.test1", LockState.LOCKED)
    hass.states.async_set("lock.test2", LockState.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get("lock.lock_group").state == LockState.LOCKED

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove("lock.test1")
    hass.states.async_remove("lock.test2")
    await hass.async_block_till_done()
    assert hass.states.get("lock.lock_group").state == STATE_UNAVAILABLE


async def test_service_calls_openable(hass: HomeAssistant) -> None:
    """Test service calls with open support."""
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: [
                {"platform": "kitchen_sink"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "lock.openable_lock",
                        "lock.another_openable_lock",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    group_state = hass.states.get("lock.lock_group")
    assert group_state.state == LockState.UNLOCKED
    assert hass.states.get("lock.openable_lock").state == LockState.LOCKED
    assert hass.states.get("lock.another_openable_lock").state == LockState.UNLOCKED

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {ATTR_ENTITY_ID: "lock.lock_group"},
        blocking=True,
    )
    assert hass.states.get("lock.openable_lock").state == LockState.OPEN
    assert hass.states.get("lock.another_openable_lock").state == LockState.OPEN

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.lock_group"},
        blocking=True,
    )
    assert hass.states.get("lock.openable_lock").state == LockState.LOCKED
    assert hass.states.get("lock.another_openable_lock").state == LockState.LOCKED

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.lock_group"},
        blocking=True,
    )
    assert hass.states.get("lock.openable_lock").state == LockState.UNLOCKED
    assert hass.states.get("lock.another_openable_lock").state == LockState.UNLOCKED


async def test_service_calls_basic(hass: HomeAssistant) -> None:
    """Test service calls without open support."""
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: [
                {"platform": "kitchen_sink"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "lock.basic_lock",
                        "lock.another_basic_lock",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    group_state = hass.states.get("lock.lock_group")
    assert group_state.state == LockState.UNLOCKED
    assert hass.states.get("lock.basic_lock").state == LockState.LOCKED
    assert hass.states.get("lock.another_basic_lock").state == LockState.UNLOCKED

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.lock_group"},
        blocking=True,
    )
    assert hass.states.get("lock.basic_lock").state == LockState.LOCKED
    assert hass.states.get("lock.another_basic_lock").state == LockState.LOCKED

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.lock_group"},
        blocking=True,
    )
    assert hass.states.get("lock.basic_lock").state == LockState.UNLOCKED
    assert hass.states.get("lock.another_basic_lock").state == LockState.UNLOCKED

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {ATTR_ENTITY_ID: "lock.lock_group"},
            blocking=True,
        )


async def test_reload(hass: HomeAssistant) -> None:
    """Test the ability to reload locks."""
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": [
                        "lock.front_door",
                        "lock.kitchen_door",
                    ],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    await hass.async_start()

    await hass.async_block_till_done()
    assert hass.states.get("lock.lock_group").state == LockState.UNLOCKED

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("lock.lock_group") is None
    assert hass.states.get("lock.inside_locks_g") is not None
    assert hass.states.get("lock.outside_locks_g") is not None


async def test_reload_with_platform_not_setup(hass: HomeAssistant) -> None:
    """Test the ability to reload locks."""
    hass.states.async_set("lock.something", LockState.UNLOCKED)
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: [
                {"platform": "demo"},
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "lock.something", "icon": "mdi:work"},
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

    assert hass.states.get("lock.lock_group") is None
    assert hass.states.get("lock.inside_locks_g") is not None
    assert hass.states.get("lock.outside_locks_g") is not None


async def test_reload_with_base_integration_platform_not_setup(
    hass: HomeAssistant,
) -> None:
    """Test the ability to reload locks."""
    assert await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "group_zero": {"entities": "lock.something", "icon": "mdi:work"},
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("lock.front_lock", LockState.LOCKED)
    hass.states.async_set("lock.back_lock", LockState.UNLOCKED)

    hass.states.async_set("lock.outside_lock", LockState.LOCKED)
    hass.states.async_set("lock.outside_lock_2", LockState.LOCKED)

    yaml_path = get_fixture_path("configuration.yaml", "group")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("lock.lock_group") is None
    assert hass.states.get("lock.inside_locks_g") is not None
    assert hass.states.get("lock.outside_locks_g") is not None
    assert hass.states.get("lock.inside_locks_g").state == LockState.UNLOCKED
    assert hass.states.get("lock.outside_locks_g").state == LockState.LOCKED


@patch.object(demo_lock, "LOCK_UNLOCK_DELAY", 0)
async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested lock group."""
    await async_setup_component(
        hass,
        LOCK_DOMAIN,
        {
            LOCK_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": DOMAIN,
                    "entities": ["lock.some_group"],
                    "name": "Nested Group",
                },
                {
                    "platform": DOMAIN,
                    "entities": [
                        "lock.front_door",
                        "lock.kitchen_door",
                    ],
                    "name": "Some Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("lock.some_group")
    assert state is not None
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "lock.front_door",
        "lock.kitchen_door",
    ]

    state = hass.states.get("lock.nested_group")
    assert state is not None
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ENTITY_ID) == ["lock.some_group"]

    # Test controlling the nested group
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.nested_group"},
        blocking=True,
    )
    assert hass.states.get("lock.front_door").state == LockState.LOCKED
    assert hass.states.get("lock.kitchen_door").state == LockState.LOCKED
    assert hass.states.get("lock.some_group").state == LockState.LOCKED
    assert hass.states.get("lock.nested_group").state == LockState.LOCKED
