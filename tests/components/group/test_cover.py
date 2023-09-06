"""The tests for the group cover platform."""
import asyncio
from datetime import timedelta

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
)
from homeassistant.components.group.cover import DEFAULT_NAME
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_UNIQUE_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

COVER_GROUP = "cover.cover_group"
DEMO_COVER = "cover.kitchen_window"
DEMO_COVER_POS = "cover.hall_window"
DEMO_COVER_TILT = "cover.living_room_window"
DEMO_TILT = "cover.tilt_demo"

CONFIG_ALL = {
    DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT],
        },
    ]
}

CONFIG_POS = {
    DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT],
        },
    ]
}

CONFIG_TILT_ONLY = {
    DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_COVER_TILT, DEMO_TILT],
        },
    ]
}

CONFIG_ATTRIBUTES = {
    DOMAIN: {
        "platform": "group",
        CONF_ENTITIES: [DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT],
        CONF_UNIQUE_ID: "unique_identifier",
    }
}


@pytest.fixture
async def setup_comp(hass, config_count):
    """Set up group cover component."""
    config, count = config_count
    with assert_setup_component(count, DOMAIN):
        await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
async def test_state(hass: HomeAssistant, setup_comp) -> None:
    """Test handling of state.

    The group state is unknown if all group members are unknown or unavailable.
    Otherwise, the group state is opening if at least one group member is opening.
    Otherwise, the group state is closing if at least one group member is closing.
    Otherwise, the group state is open if at least one group member is open.
    Otherwise, the group state is closed.
    """
    state = hass.states.get(COVER_GROUP)
    # No entity has a valid state -> group state unavailable
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_FRIENDLY_NAME] == DEFAULT_NAME
    assert ATTR_ENTITY_ID not in state.attributes
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Test group members exposed as attribute
    hass.states.async_set(DEMO_COVER, STATE_UNKNOWN, {})
    await hass.async_block_till_done()
    state = hass.states.get(COVER_GROUP)
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_COVER,
        DEMO_COVER_POS,
        DEMO_COVER_TILT,
        DEMO_TILT,
    ]

    # The group state is unavailable if all group members are unavailable.
    hass.states.async_set(DEMO_COVER, STATE_UNAVAILABLE, {})
    hass.states.async_set(DEMO_COVER_POS, STATE_UNAVAILABLE, {})
    hass.states.async_set(DEMO_COVER_TILT, STATE_UNAVAILABLE, {})
    hass.states.async_set(DEMO_TILT, STATE_UNAVAILABLE, {})
    await hass.async_block_till_done()
    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_UNAVAILABLE

    # The group state is unknown if all group members are unknown or unavailable.
    for state_1 in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        for state_2 in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            for state_3 in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, STATE_UNKNOWN, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == STATE_UNKNOWN

    # At least one member opening -> group opening
    for state_1 in (
        STATE_CLOSED,
        STATE_CLOSING,
        STATE_OPEN,
        STATE_OPENING,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            STATE_CLOSED,
            STATE_CLOSING,
            STATE_OPEN,
            STATE_OPENING,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                STATE_CLOSED,
                STATE_CLOSING,
                STATE_OPEN,
                STATE_OPENING,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, STATE_OPENING, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == STATE_OPENING

    # At least one member closing -> group closing
    for state_1 in (
        STATE_CLOSED,
        STATE_CLOSING,
        STATE_OPEN,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            STATE_CLOSED,
            STATE_CLOSING,
            STATE_OPEN,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                STATE_CLOSED,
                STATE_CLOSING,
                STATE_OPEN,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, STATE_CLOSING, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == STATE_CLOSING

    # At least one member open -> group open
    for state_1 in (STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE, STATE_UNKNOWN):
        for state_2 in (STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE, STATE_UNKNOWN):
            for state_3 in (STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE, STATE_UNKNOWN):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, STATE_OPEN, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == STATE_OPEN

    # At least one member closed -> group closed
    for state_1 in (STATE_CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
        for state_2 in (STATE_CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
            for state_3 in (STATE_CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, STATE_CLOSED, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == STATE_CLOSED

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove(DEMO_COVER)
    hass.states.async_remove(DEMO_COVER_POS)
    hass.states.async_remove(DEMO_COVER_TILT)
    hass.states.async_remove(DEMO_TILT)
    await hass.async_block_till_done()
    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
async def test_attributes(hass: HomeAssistant, setup_comp) -> None:
    """Test handling of state attributes."""
    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes[ATTR_FRIENDLY_NAME] == DEFAULT_NAME
    assert ATTR_ENTITY_ID not in state.attributes
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Set entity as closed
    hass.states.async_set(DEMO_COVER, STATE_CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_COVER,
        DEMO_COVER_POS,
        DEMO_COVER_TILT,
        DEMO_TILT,
    ]

    # Set entity as opening
    hass.states.async_set(DEMO_COVER, STATE_OPENING, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPENING

    # Set entity as closing
    hass.states.async_set(DEMO_COVER, STATE_CLOSING, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_CLOSING

    # Set entity as unknown again
    hass.states.async_set(DEMO_COVER, STATE_UNKNOWN, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_UNKNOWN

    # Add Entity that supports open / close / stop
    hass.states.async_set(DEMO_COVER, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 11
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Add Entity that supports set_cover_position
    hass.states.async_set(
        DEMO_COVER_POS,
        STATE_OPEN,
        {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 70},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 15
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Add Entity that supports open tilt / close tilt / stop tilt
    hass.states.async_set(DEMO_TILT, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 112})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 127
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Add Entity that supports set_tilt_position
    hass.states.async_set(
        DEMO_COVER_TILT,
        STATE_OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 255
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    # ### Test state when group members have different states ###
    # ##########################

    # Covers
    hass.states.async_set(
        DEMO_COVER, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 100}
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 244
    assert state.attributes[ATTR_CURRENT_POSITION] == 85  # (70 + 100) / 2
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    hass.states.async_remove(DEMO_COVER)
    hass.states.async_remove(DEMO_COVER_POS)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 240
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    # Tilts
    hass.states.async_set(
        DEMO_TILT,
        STATE_OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 100},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 128
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 80  # (60 + 100) / 2

    hass.states.async_remove(DEMO_COVER_TILT)
    hass.states.async_set(DEMO_TILT, STATE_CLOSED)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_CLOSED
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Group member has set assumed_state
    hass.states.async_set(DEMO_TILT, STATE_CLOSED, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert ATTR_ASSUMED_STATE not in state.attributes

    # Test entity registry integration
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(COVER_GROUP)
    assert entry
    assert entry.unique_id == "unique_identifier"


@pytest.mark.parametrize("config_count", [(CONFIG_TILT_ONLY, 2)])
async def test_cover_that_only_supports_tilt_removed(
    hass: HomeAssistant, setup_comp
) -> None:
    """Test removing a cover that support tilt."""
    hass.states.async_set(
        DEMO_COVER_TILT,
        STATE_OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60},
    )
    hass.states.async_set(
        DEMO_TILT,
        STATE_OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60},
    )
    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_FRIENDLY_NAME] == DEFAULT_NAME
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_COVER_TILT,
        DEMO_TILT,
    ]
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION in state.attributes

    hass.states.async_remove(DEMO_COVER_TILT)
    hass.states.async_set(DEMO_TILT, STATE_CLOSED)
    await hass.async_block_till_done()


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_open_covers(hass: HomeAssistant, setup_comp) -> None:
    """Test open cover function."""
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    assert hass.states.get(DEMO_COVER).state == STATE_OPEN
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 100
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_close_covers(hass: HomeAssistant, setup_comp) -> None:
    """Test close cover function."""
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    assert hass.states.get(DEMO_COVER).state == STATE_CLOSED
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 0
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_toggle_covers(hass: HomeAssistant, setup_comp) -> None:
    """Test toggle cover function."""
    # Start covers in open state
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN

    # Toggle will close covers
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    assert hass.states.get(DEMO_COVER).state == STATE_CLOSED
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 0
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 0

    # Toggle again will open covers
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    assert hass.states.get(DEMO_COVER).state == STATE_OPEN
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 100
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_stop_covers(hass: HomeAssistant, setup_comp) -> None:
    """Test stop cover function."""
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50  # (20 + 80) / 2

    assert hass.states.get(DEMO_COVER).state == STATE_OPEN
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 20
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 80


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_set_cover_position(hass: HomeAssistant, setup_comp) -> None:
    """Test set cover position function."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: COVER_GROUP, ATTR_POSITION: 50},
        blocking=True,
    )
    for _ in range(4):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    assert hass.states.get(DEMO_COVER).state == STATE_CLOSED
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 50
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_open_tilts(hass: HomeAssistant, setup_comp) -> None:
    """Test open tilt function."""
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    assert (
        hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 100
    )


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_close_tilts(hass: HomeAssistant, setup_comp) -> None:
    """Test close tilt function."""
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 0


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_toggle_tilts(hass: HomeAssistant, setup_comp) -> None:
    """Test toggle tilt function."""
    # Start tilted open
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    assert (
        hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 100
    )

    # Toggle will tilt closed
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Toggle again will tilt open
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    assert (
        hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 100
    )


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_stop_tilts(hass: HomeAssistant, setup_comp) -> None:
    """Test stop tilts function."""
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER_TILT, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 60


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
async def test_set_tilt_positions(hass: HomeAssistant, setup_comp) -> None:
    """Test set tilt position function."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: COVER_GROUP, ATTR_TILT_POSITION: 80},
        blocking=True,
    )
    for _ in range(3):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 80

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 80


@pytest.mark.parametrize("config_count", [(CONFIG_POS, 2)])
async def test_is_opening_closing(hass: HomeAssistant, setup_comp) -> None:
    """Test is_opening property."""
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    await hass.async_block_till_done()

    # Both covers opening -> opening
    assert hass.states.get(DEMO_COVER_POS).state == STATE_OPENING
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_OPENING
    assert hass.states.get(COVER_GROUP).state == STATE_OPENING

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )

    # Both covers closing -> closing
    assert hass.states.get(DEMO_COVER_POS).state == STATE_CLOSING
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_CLOSING
    assert hass.states.get(COVER_GROUP).state == STATE_CLOSING

    hass.states.async_set(DEMO_COVER_POS, STATE_OPENING, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()

    # Closing + Opening -> Opening
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == STATE_OPENING
    assert hass.states.get(COVER_GROUP).state == STATE_OPENING

    hass.states.async_set(DEMO_COVER_POS, STATE_CLOSING, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()

    # Both covers closing -> closing
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == STATE_CLOSING
    assert hass.states.get(COVER_GROUP).state == STATE_CLOSING

    # Closed + Closing -> Closing
    hass.states.async_set(DEMO_COVER_POS, STATE_CLOSED, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == STATE_CLOSED
    assert hass.states.get(COVER_GROUP).state == STATE_CLOSING

    # Open + Closing -> Closing
    hass.states.async_set(DEMO_COVER_POS, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == STATE_OPEN
    assert hass.states.get(COVER_GROUP).state == STATE_CLOSING

    # Closed + Opening -> Closing
    hass.states.async_set(DEMO_COVER_TILT, STATE_OPENING, {ATTR_SUPPORTED_FEATURES: 11})
    hass.states.async_set(DEMO_COVER_POS, STATE_CLOSED, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_OPENING
    assert hass.states.get(DEMO_COVER_POS).state == STATE_CLOSED
    assert hass.states.get(COVER_GROUP).state == STATE_OPENING

    # Open + Opening -> Closing
    hass.states.async_set(DEMO_COVER_POS, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_OPENING
    assert hass.states.get(DEMO_COVER_POS).state == STATE_OPEN
    assert hass.states.get(COVER_GROUP).state == STATE_OPENING


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested cover group."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"platform": "demo"},
                {
                    "platform": "group",
                    "entities": ["cover.bedroom_group"],
                    "name": "Nested Group",
                },
                {
                    "platform": "group",
                    CONF_ENTITIES: [DEMO_COVER_POS, DEMO_COVER_TILT],
                    "name": "Bedroom Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("cover.bedroom_group")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_ENTITY_ID) == [DEMO_COVER_POS, DEMO_COVER_TILT]

    state = hass.states.get("cover.nested_group")
    assert state is not None
    assert state.state == STATE_OPEN
    assert state.attributes.get(ATTR_ENTITY_ID) == ["cover.bedroom_group"]

    # Test controlling the nested group
    async with asyncio.timeout(0.5):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.nested_group"},
            blocking=True,
        )
    assert hass.states.get(DEMO_COVER_POS).state == STATE_CLOSING
    assert hass.states.get(DEMO_COVER_TILT).state == STATE_CLOSING
    assert hass.states.get("cover.bedroom_group").state == STATE_CLOSING
    assert hass.states.get("cover.nested_group").state == STATE_CLOSING
