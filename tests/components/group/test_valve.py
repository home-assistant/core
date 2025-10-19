"""The tests for the group valve platform."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.group.valve import DEFAULT_NAME
from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    ValveState,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_UNIQUE_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    SERVICE_TOGGLE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

VALVE_GROUP = "valve.valve_group"
DEMO_VALVE1 = "valve.front_garden"
DEMO_VALVE2 = "valve.orchard"
DEMO_VALVE_POS1 = "valve.back_garden"
DEMO_VALVE_POS2 = "valve.trees"

CONFIG_ALL = {
    VALVE_DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_VALVE1, DEMO_VALVE2, DEMO_VALVE_POS1, DEMO_VALVE_POS2],
        },
    ]
}

CONFIG_POS = {
    VALVE_DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_VALVE_POS1, DEMO_VALVE_POS2],
        },
    ]
}


CONFIG_ATTRIBUTES = {
    VALVE_DOMAIN: {
        "platform": "group",
        CONF_ENTITIES: [DEMO_VALVE1, DEMO_VALVE2, DEMO_VALVE_POS1, DEMO_VALVE_POS2],
        CONF_UNIQUE_ID: "unique_identifier",
    }
}


@pytest.fixture(scope="module", autouse=True)
def patch_demo_open_close_delay():
    """Patch demo valve open/close delay."""
    with patch("homeassistant.components.demo.valve.OPEN_CLOSE_DELAY", 0):
        yield


@pytest.fixture
async def setup_comp(
    hass: HomeAssistant, config_count: tuple[dict[str, Any], int]
) -> None:
    """Set up group valve component."""
    config, count = config_count
    with assert_setup_component(count, VALVE_DOMAIN):
        await async_setup_component(hass, VALVE_DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
@pytest.mark.usefixtures("setup_comp")
async def test_state(hass: HomeAssistant) -> None:
    """Test handling of state.

    The group state is unknown if all group members are unknown or unavailable.
    Otherwise, the group state is opening if at least one group member is opening.
    Otherwise, the group state is closing if at least one group member is closing.
    Otherwise, the group state is open if at least one group member is open.
    Otherwise, the group state is closed.
    """
    state = hass.states.get(VALVE_GROUP)
    # No entity has a valid state -> group state unavailable
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_FRIENDLY_NAME] == DEFAULT_NAME
    assert ATTR_ENTITY_ID not in state.attributes
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes

    # Test group members exposed as attribute
    hass.states.async_set(DEMO_VALVE1, STATE_UNKNOWN, {})
    await hass.async_block_till_done()
    state = hass.states.get(VALVE_GROUP)
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_VALVE1,
        DEMO_VALVE2,
        DEMO_VALVE_POS1,
        DEMO_VALVE_POS2,
    ]

    # The group state is unavailable if all group members are unavailable.
    hass.states.async_set(DEMO_VALVE1, STATE_UNAVAILABLE, {})
    hass.states.async_set(DEMO_VALVE_POS1, STATE_UNAVAILABLE, {})
    hass.states.async_set(DEMO_VALVE_POS2, STATE_UNAVAILABLE, {})
    hass.states.async_set(DEMO_VALVE2, STATE_UNAVAILABLE, {})
    await hass.async_block_till_done()
    state = hass.states.get(VALVE_GROUP)
    assert state.state == STATE_UNAVAILABLE

    # The group state is unknown if all group members are unknown or unavailable.
    for state_1 in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        for state_2 in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            for state_3 in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                hass.states.async_set(DEMO_VALVE1, state_1, {})
                hass.states.async_set(DEMO_VALVE_POS1, state_2, {})
                hass.states.async_set(DEMO_VALVE_POS2, state_3, {})
                hass.states.async_set(DEMO_VALVE2, STATE_UNKNOWN, {})
                await hass.async_block_till_done()
                state = hass.states.get(VALVE_GROUP)
                assert state.state == STATE_UNKNOWN

    # At least one member opening -> group opening
    for state_1 in (
        ValveState.CLOSED,
        ValveState.CLOSING,
        ValveState.OPEN,
        ValveState.OPENING,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            ValveState.CLOSED,
            ValveState.CLOSING,
            ValveState.OPEN,
            ValveState.OPENING,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                ValveState.CLOSED,
                ValveState.CLOSING,
                ValveState.OPEN,
                ValveState.OPENING,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_VALVE1, state_1, {})
                hass.states.async_set(DEMO_VALVE_POS1, state_2, {})
                hass.states.async_set(DEMO_VALVE_POS2, state_3, {})
                hass.states.async_set(DEMO_VALVE2, ValveState.OPENING, {})
                await hass.async_block_till_done()
                state = hass.states.get(VALVE_GROUP)
                assert state.state == ValveState.OPENING

    # At least one member closing -> group closing
    for state_1 in (
        ValveState.CLOSED,
        ValveState.CLOSING,
        ValveState.OPEN,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            ValveState.CLOSED,
            ValveState.CLOSING,
            ValveState.OPEN,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                ValveState.CLOSED,
                ValveState.CLOSING,
                ValveState.OPEN,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_VALVE1, state_1, {})
                hass.states.async_set(DEMO_VALVE_POS1, state_2, {})
                hass.states.async_set(DEMO_VALVE_POS2, state_3, {})
                hass.states.async_set(DEMO_VALVE2, ValveState.CLOSING, {})
                await hass.async_block_till_done()
                state = hass.states.get(VALVE_GROUP)
                assert state.state == ValveState.CLOSING

    # At least one member open -> group open
    for state_1 in (
        ValveState.CLOSED,
        ValveState.OPEN,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            ValveState.CLOSED,
            ValveState.OPEN,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                ValveState.CLOSED,
                ValveState.OPEN,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_VALVE1, state_1, {})
                hass.states.async_set(DEMO_VALVE_POS1, state_2, {})
                hass.states.async_set(DEMO_VALVE_POS2, state_3, {})
                hass.states.async_set(DEMO_VALVE2, ValveState.OPEN, {})
                await hass.async_block_till_done()
                state = hass.states.get(VALVE_GROUP)
                assert state.state == ValveState.OPEN

    # At least one member closed -> group closed
    for state_1 in (ValveState.CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
        for state_2 in (ValveState.CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
            for state_3 in (ValveState.CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
                hass.states.async_set(DEMO_VALVE1, state_1, {})
                hass.states.async_set(DEMO_VALVE_POS1, state_2, {})
                hass.states.async_set(DEMO_VALVE_POS2, state_3, {})
                hass.states.async_set(DEMO_VALVE2, ValveState.CLOSED, {})
                await hass.async_block_till_done()
                state = hass.states.get(VALVE_GROUP)
                assert state.state == ValveState.CLOSED

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove(DEMO_VALVE1)
    hass.states.async_remove(DEMO_VALVE_POS1)
    hass.states.async_remove(DEMO_VALVE_POS2)
    hass.states.async_remove(DEMO_VALVE2)
    await hass.async_block_till_done()
    state = hass.states.get(VALVE_GROUP)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
@pytest.mark.usefixtures("setup_comp")
async def test_attributes(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test handling of state attributes."""
    state = hass.states.get(VALVE_GROUP)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_FRIENDLY_NAME] == DEFAULT_NAME
    assert ATTR_ENTITY_ID not in state.attributes
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes

    # Set entity as closed
    hass.states.async_set(DEMO_VALVE1, ValveState.CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.CLOSED
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_VALVE1,
        DEMO_VALVE2,
        DEMO_VALVE_POS1,
        DEMO_VALVE_POS2,
    ]

    # Set entity as opening
    hass.states.async_set(DEMO_VALVE1, ValveState.OPENING, {})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPENING

    # Set entity as closing
    hass.states.async_set(DEMO_VALVE1, ValveState.CLOSING, {})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.CLOSING

    # Set entity as unknown again
    hass.states.async_set(DEMO_VALVE1, STATE_UNKNOWN, {})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == STATE_UNKNOWN

    # Add Entity that supports open / close / stop
    hass.states.async_set(DEMO_VALVE1, ValveState.OPEN, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 11
    assert ATTR_CURRENT_POSITION not in state.attributes

    # Add Entity that supports set_valve_position
    hass.states.async_set(
        DEMO_VALVE_POS1,
        ValveState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 70},
    )
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 15
    assert state.attributes[ATTR_CURRENT_POSITION] == 70

    ### Test state when group members have different states ###

    # Valves
    hass.states.async_remove(DEMO_VALVE_POS1)
    hass.states.async_remove(DEMO_VALVE_POS2)
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 11
    assert ATTR_CURRENT_POSITION not in state.attributes

    # Test entity registry integration
    entry = entity_registry.async_get(VALVE_GROUP)
    assert entry
    assert entry.unique_id == "unique_identifier"


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_open_valves(hass: HomeAssistant) -> None:
    """Test open valve function."""
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    assert hass.states.get(DEMO_VALVE1).state == ValveState.OPEN
    assert hass.states.get(DEMO_VALVE_POS1).attributes[ATTR_CURRENT_POSITION] == 100
    assert hass.states.get(DEMO_VALVE_POS2).attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_close_valves(hass: HomeAssistant) -> None:
    """Test close valve function."""
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    assert hass.states.get(DEMO_VALVE1).state == ValveState.CLOSED
    assert hass.states.get(DEMO_VALVE_POS1).attributes[ATTR_CURRENT_POSITION] == 0
    assert hass.states.get(DEMO_VALVE_POS2).attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_toggle_valves(hass: HomeAssistant) -> None:
    """Test toggle valve function."""
    # Start valves in open state
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN

    # Toggle will close valves
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    assert hass.states.get(DEMO_VALVE1).state == ValveState.CLOSED
    assert hass.states.get(DEMO_VALVE_POS1).attributes[ATTR_CURRENT_POSITION] == 0
    assert hass.states.get(DEMO_VALVE_POS2).attributes[ATTR_CURRENT_POSITION] == 0

    # Toggle again will open valves
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    assert hass.states.get(DEMO_VALVE1).state == ValveState.OPEN
    assert hass.states.get(DEMO_VALVE_POS1).attributes[ATTR_CURRENT_POSITION] == 100
    assert hass.states.get(DEMO_VALVE_POS2).attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_stop_valves(hass: HomeAssistant) -> None:
    """Test stop valve function."""
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPENING

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_STOP_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 60  # (40 + 80) / 2

    assert hass.states.get(DEMO_VALVE1).state == ValveState.OPEN
    assert hass.states.get(DEMO_VALVE_POS1).attributes[ATTR_CURRENT_POSITION] == 80
    assert hass.states.get(DEMO_VALVE_POS2).attributes[ATTR_CURRENT_POSITION] == 40


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_set_valve_position(hass: HomeAssistant) -> None:
    """Test set valve position function."""
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: VALVE_GROUP, ATTR_POSITION: 50},
        blocking=True,
    )
    for _ in range(4):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.state == ValveState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    assert hass.states.get(DEMO_VALVE1).state == ValveState.OPEN
    assert hass.states.get(DEMO_VALVE_POS1).attributes[ATTR_CURRENT_POSITION] == 50
    assert hass.states.get(DEMO_VALVE_POS2).attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.parametrize("config_count", [(CONFIG_POS, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_is_opening_closing(hass: HomeAssistant) -> None:
    """Test is_opening property."""
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )
    await hass.async_block_till_done()

    # Both valves opening -> opening
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.OPENING
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.OPENING
    assert hass.states.get(VALVE_GROUP).state == ValveState.OPENING

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_CLOSE_VALVE, {ATTR_ENTITY_ID: VALVE_GROUP}, blocking=True
    )

    # Both valves closing -> closing
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.CLOSING
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.CLOSING
    assert hass.states.get(VALVE_GROUP).state == ValveState.CLOSING

    hass.states.async_set(
        DEMO_VALVE_POS1, ValveState.OPENING, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()

    # Closing + Opening -> Opening
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.CLOSING
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.OPENING
    assert hass.states.get(VALVE_GROUP).state == ValveState.OPENING

    hass.states.async_set(
        DEMO_VALVE_POS1, ValveState.CLOSING, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()

    # Both valves closing -> closing
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.CLOSING
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.CLOSING
    assert hass.states.get(VALVE_GROUP).state == ValveState.CLOSING

    # Closed + Closing -> Closing
    hass.states.async_set(
        DEMO_VALVE_POS1, ValveState.CLOSED, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.CLOSING
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.CLOSED
    assert hass.states.get(VALVE_GROUP).state == ValveState.CLOSING

    # Open + Closing -> Closing
    hass.states.async_set(
        DEMO_VALVE_POS1, ValveState.OPEN, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.CLOSING
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.OPEN
    assert hass.states.get(VALVE_GROUP).state == ValveState.CLOSING

    # Closed + Opening -> Closing
    hass.states.async_set(
        DEMO_VALVE_POS2, ValveState.OPENING, {ATTR_SUPPORTED_FEATURES: 11}
    )
    hass.states.async_set(
        DEMO_VALVE_POS1, ValveState.CLOSED, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.OPENING
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.CLOSED
    assert hass.states.get(VALVE_GROUP).state == ValveState.OPENING

    # Open + Opening -> Closing
    hass.states.async_set(
        DEMO_VALVE_POS1, ValveState.OPEN, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.OPENING
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.OPEN
    assert hass.states.get(VALVE_GROUP).state == ValveState.OPENING


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
@pytest.mark.usefixtures("setup_comp")
async def test_assumed_state(hass: HomeAssistant) -> None:
    """Test assumed_state attribute behavior."""
    # No members with assumed_state -> group doesn't have assumed_state in attributes
    hass.states.async_set(DEMO_VALVE1, ValveState.OPEN, {})
    hass.states.async_set(DEMO_VALVE_POS1, ValveState.OPEN, {})
    hass.states.async_set(DEMO_VALVE_POS2, ValveState.CLOSED, {})
    hass.states.async_set(DEMO_VALVE2, ValveState.CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert ATTR_ASSUMED_STATE not in state.attributes

    # One member with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(DEMO_VALVE1, ValveState.OPEN, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Multiple members with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(
        DEMO_VALVE_POS2, ValveState.CLOSED, {ATTR_ASSUMED_STATE: True}
    )
    hass.states.async_set(DEMO_VALVE2, ValveState.CLOSED, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Unavailable member with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(DEMO_VALVE1, ValveState.OPEN, {})
    hass.states.async_set(DEMO_VALVE_POS2, ValveState.CLOSED, {})
    hass.states.async_set(DEMO_VALVE2, STATE_UNAVAILABLE, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Unknown member with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(DEMO_VALVE2, STATE_UNKNOWN, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # All members without assumed_state -> group doesn't have assumed_state in attributes
    hass.states.async_set(DEMO_VALVE2, ValveState.CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(VALVE_GROUP)
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested valve group."""
    await async_setup_component(
        hass,
        VALVE_DOMAIN,
        {
            VALVE_DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": "group",
                    "entities": ["valve.bedroom_group"],
                    "name": "Nested Group",
                },
                {
                    "platform": "group",
                    CONF_ENTITIES: [DEMO_VALVE_POS1, DEMO_VALVE_POS2],
                    "name": "Bedroom Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("valve.bedroom_group")
    assert state is not None
    assert state.state == ValveState.OPEN
    assert state.attributes.get(ATTR_ENTITY_ID) == [DEMO_VALVE_POS1, DEMO_VALVE_POS2]

    state = hass.states.get("valve.nested_group")
    assert state is not None
    assert state.state == ValveState.OPEN
    assert state.attributes.get(ATTR_ENTITY_ID) == ["valve.bedroom_group"]

    # Test controlling the nested group
    async with asyncio.timeout(0.5):
        await hass.services.async_call(
            VALVE_DOMAIN,
            SERVICE_CLOSE_VALVE,
            {ATTR_ENTITY_ID: "valve.nested_group"},
            blocking=True,
        )
    assert hass.states.get(DEMO_VALVE_POS1).state == ValveState.CLOSING
    assert hass.states.get(DEMO_VALVE_POS2).state == ValveState.CLOSING
    assert hass.states.get("valve.bedroom_group").state == ValveState.CLOSING
    assert hass.states.get("valve.nested_group").state == ValveState.CLOSING
