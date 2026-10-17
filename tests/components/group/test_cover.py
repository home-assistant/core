"""The tests for the group cover platform."""

import asyncio
from contextlib import ExitStack
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_SPEED,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverState,
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    assert_setup_component,
    async_fire_time_changed,
    setup_test_component_platform,
)
from tests.components.cover.common import MockCover

COVER_GROUP = "cover.cover_group"
DEMO_COVER = "cover.kitchen_window"
DEMO_COVER_POS = "cover.hall_window"
DEMO_COVER_TILT = "cover.living_room_window"
DEMO_TILT = "cover.tilt_demo"
SLOW_FAST_COVER = "cover.slow_fast"
SILENT_FAST_COVER = "cover.silent_fast"
NO_SPEED_COVER = "cover.no_speed"
OUTER_GROUP = "cover.outer_group"

CONFIG_ALL = {
    COVER_DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT],
        },
    ]
}

CONFIG_POS = {
    COVER_DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT],
        },
    ]
}

CONFIG_TILT_ONLY = {
    COVER_DOMAIN: [
        {"platform": "demo"},
        {
            "platform": "group",
            CONF_ENTITIES: [DEMO_COVER_TILT, DEMO_TILT],
        },
    ]
}

CONFIG_ATTRIBUTES = {
    COVER_DOMAIN: {
        "platform": "group",
        CONF_ENTITIES: [DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT],
        CONF_UNIQUE_ID: "unique_identifier",
    }
}


@pytest.fixture
async def setup_comp(
    hass: HomeAssistant, config_count: tuple[dict[str, Any], int]
) -> None:
    """Set up group cover component."""
    config, count = config_count
    with assert_setup_component(count, COVER_DOMAIN):
        await async_setup_component(hass, COVER_DOMAIN, config)
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
        CoverState.CLOSED,
        CoverState.CLOSING,
        CoverState.OPEN,
        CoverState.OPENING,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            CoverState.CLOSED,
            CoverState.CLOSING,
            CoverState.OPEN,
            CoverState.OPENING,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                CoverState.CLOSED,
                CoverState.CLOSING,
                CoverState.OPEN,
                CoverState.OPENING,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, CoverState.OPENING, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == CoverState.OPENING

    # At least one member closing -> group closing
    for state_1 in (
        CoverState.CLOSED,
        CoverState.CLOSING,
        CoverState.OPEN,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            CoverState.CLOSED,
            CoverState.CLOSING,
            CoverState.OPEN,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                CoverState.CLOSED,
                CoverState.CLOSING,
                CoverState.OPEN,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, CoverState.CLOSING, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == CoverState.CLOSING

    # At least one member open -> group open
    for state_1 in (
        CoverState.CLOSED,
        CoverState.OPEN,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        for state_2 in (
            CoverState.CLOSED,
            CoverState.OPEN,
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            for state_3 in (
                CoverState.CLOSED,
                CoverState.OPEN,
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, CoverState.OPEN, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == CoverState.OPEN

    # At least one member closed -> group closed
    for state_1 in (CoverState.CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
        for state_2 in (CoverState.CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
            for state_3 in (CoverState.CLOSED, STATE_UNAVAILABLE, STATE_UNKNOWN):
                hass.states.async_set(DEMO_COVER, state_1, {})
                hass.states.async_set(DEMO_COVER_POS, state_2, {})
                hass.states.async_set(DEMO_COVER_TILT, state_3, {})
                hass.states.async_set(DEMO_TILT, CoverState.CLOSED, {})
                await hass.async_block_till_done()
                state = hass.states.get(COVER_GROUP)
                assert state.state == CoverState.CLOSED

    # All group members removed from the state machine -> unavailable
    hass.states.async_remove(DEMO_COVER)
    hass.states.async_remove(DEMO_COVER_POS)
    hass.states.async_remove(DEMO_COVER_TILT)
    hass.states.async_remove(DEMO_TILT)
    await hass.async_block_till_done()
    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
@pytest.mark.usefixtures("setup_comp")
async def test_attributes(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
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
    hass.states.async_set(DEMO_COVER, CoverState.CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_COVER,
        DEMO_COVER_POS,
        DEMO_COVER_TILT,
        DEMO_TILT,
    ]

    # Set entity as opening
    hass.states.async_set(DEMO_COVER, CoverState.OPENING, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPENING

    # Set entity as closing
    hass.states.async_set(DEMO_COVER, CoverState.CLOSING, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.CLOSING

    # Set entity as unknown again
    hass.states.async_set(DEMO_COVER, STATE_UNKNOWN, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == STATE_UNKNOWN

    # Add Entity that supports open / close / stop
    hass.states.async_set(DEMO_COVER, CoverState.OPEN, {ATTR_SUPPORTED_FEATURES: 11})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 11
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Add Entity that supports set_cover_position
    hass.states.async_set(
        DEMO_COVER_POS,
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 70},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 15
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Add Entity that supports open tilt / close tilt / stop tilt
    hass.states.async_set(DEMO_TILT, CoverState.OPEN, {ATTR_SUPPORTED_FEATURES: 112})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 127
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Add Entity that supports set_tilt_position
    hass.states.async_set(
        DEMO_COVER_TILT,
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 255
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    # ### Test state when group members have different states ###
    # ##########################

    # Covers
    hass.states.async_set(
        DEMO_COVER,
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 100},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 244
    assert state.attributes[ATTR_CURRENT_POSITION] == 85  # (70 + 100) / 2
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    hass.states.async_remove(DEMO_COVER)
    hass.states.async_remove(DEMO_COVER_POS)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 240
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    # Tilts
    hass.states.async_set(
        DEMO_TILT,
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 100},
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 128
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 80  # (60 + 100) / 2

    hass.states.async_remove(DEMO_COVER_TILT)
    hass.states.async_set(DEMO_TILT, CoverState.CLOSED)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.CLOSED
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Test entity registry integration
    entry = entity_registry.async_get(COVER_GROUP)
    assert entry
    assert entry.unique_id == "unique_identifier"


@pytest.mark.parametrize("config_count", [(CONFIG_TILT_ONLY, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_cover_that_only_supports_tilt_removed(hass: HomeAssistant) -> None:
    """Test removing a cover that support tilt."""
    hass.states.async_set(
        DEMO_COVER_TILT,
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60},
    )
    hass.states.async_set(
        DEMO_TILT,
        CoverState.OPEN,
        {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60},
    )
    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_FRIENDLY_NAME] == DEFAULT_NAME
    assert state.attributes[ATTR_ENTITY_ID] == [
        DEMO_COVER_TILT,
        DEMO_TILT,
    ]
    assert ATTR_ASSUMED_STATE not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION in state.attributes

    hass.states.async_remove(DEMO_COVER_TILT)
    hass.states.async_set(DEMO_TILT, CoverState.CLOSED)
    await hass.async_block_till_done()


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_open_covers(hass: HomeAssistant) -> None:
    """Test open cover function."""
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    assert hass.states.get(DEMO_COVER).state == CoverState.OPEN
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 100
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_close_covers(hass: HomeAssistant) -> None:
    """Test close cover function."""
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    assert hass.states.get(DEMO_COVER).state == CoverState.CLOSED
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 0
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_toggle_covers(hass: HomeAssistant) -> None:
    """Test toggle cover function."""
    # Start covers in open state
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN

    # Toggle will close covers
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    assert hass.states.get(DEMO_COVER).state == CoverState.CLOSED
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 0
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 0

    # Toggle again will open covers
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100

    assert hass.states.get(DEMO_COVER).state == CoverState.OPEN
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 100
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_stop_covers(hass: HomeAssistant) -> None:
    """Test stop cover function."""
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50  # (20 + 80) / 2

    assert hass.states.get(DEMO_COVER).state == CoverState.OPEN
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 20
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 80


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_set_cover_position(hass: HomeAssistant) -> None:
    """Test set cover position function."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: COVER_GROUP, ATTR_POSITION: 50},
        blocking=True,
    )
    for _ in range(4):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    assert hass.states.get(DEMO_COVER).state == CoverState.CLOSED
    assert hass.states.get(DEMO_COVER_POS).attributes[ATTR_CURRENT_POSITION] == 50
    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_open_tilts(hass: HomeAssistant) -> None:
    """Test open tilt function."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    assert (
        hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 100
    )


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_close_tilts(hass: HomeAssistant) -> None:
    """Test close tilt function."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    for _ in range(5):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 0


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_toggle_tilts(hass: HomeAssistant) -> None:
    """Test toggle tilt function."""
    # Start tilted open
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    assert (
        hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 100
    )

    # Toggle will tilt closed
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Toggle again will tilt open
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_TOGGLE_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    assert (
        hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 100
    )


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_stop_tilts(hass: HomeAssistant) -> None:
    """Test stop tilts function."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: COVER_GROUP},
        blocking=True,
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 60

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 60


@pytest.mark.parametrize("config_count", [(CONFIG_ALL, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_set_tilt_positions(hass: HomeAssistant) -> None:
    """Test set tilt position function."""
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: COVER_GROUP, ATTR_TILT_POSITION: 80},
        blocking=True,
    )
    for _ in range(3):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 80

    assert hass.states.get(DEMO_COVER_TILT).attributes[ATTR_CURRENT_TILT_POSITION] == 80


@pytest.mark.parametrize("config_count", [(CONFIG_POS, 2)])
@pytest.mark.usefixtures("setup_comp")
async def test_is_opening_closing(hass: HomeAssistant) -> None:
    """Test is_opening property."""
    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )
    await hass.async_block_till_done()

    # Both covers opening -> opening
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.OPENING
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.OPENING
    assert hass.states.get(COVER_GROUP).state == CoverState.OPENING

    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: COVER_GROUP}, blocking=True
    )

    # Both covers closing -> closing
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.CLOSING
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.CLOSING
    assert hass.states.get(COVER_GROUP).state == CoverState.CLOSING

    hass.states.async_set(
        DEMO_COVER_POS, CoverState.OPENING, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()

    # Closing + Opening -> Opening
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.OPENING
    assert hass.states.get(COVER_GROUP).state == CoverState.OPENING

    hass.states.async_set(
        DEMO_COVER_POS, CoverState.CLOSING, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()

    # Both covers closing -> closing
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.CLOSING
    assert hass.states.get(COVER_GROUP).state == CoverState.CLOSING

    # Closed + Closing -> Closing
    hass.states.async_set(
        DEMO_COVER_POS, CoverState.CLOSED, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.CLOSED
    assert hass.states.get(COVER_GROUP).state == CoverState.CLOSING

    # Open + Closing -> Closing
    hass.states.async_set(
        DEMO_COVER_POS, CoverState.OPEN, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.CLOSING
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.OPEN
    assert hass.states.get(COVER_GROUP).state == CoverState.CLOSING

    # Closed + Opening -> Closing
    hass.states.async_set(
        DEMO_COVER_TILT, CoverState.OPENING, {ATTR_SUPPORTED_FEATURES: 11}
    )
    hass.states.async_set(
        DEMO_COVER_POS, CoverState.CLOSED, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.OPENING
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.CLOSED
    assert hass.states.get(COVER_GROUP).state == CoverState.OPENING

    # Open + Opening -> Closing
    hass.states.async_set(
        DEMO_COVER_POS, CoverState.OPEN, {ATTR_SUPPORTED_FEATURES: 11}
    )
    await hass.async_block_till_done()
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.OPENING
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.OPEN
    assert hass.states.get(COVER_GROUP).state == CoverState.OPENING


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
@pytest.mark.usefixtures("setup_comp")
async def test_assumed_state(hass: HomeAssistant) -> None:
    """Test assumed_state attribute behavior."""
    # No members with assumed_state -> group doesn't have assumed_state in attributes
    hass.states.async_set(DEMO_COVER, CoverState.OPEN, {})
    hass.states.async_set(DEMO_COVER_POS, CoverState.OPEN, {})
    hass.states.async_set(DEMO_COVER_TILT, CoverState.CLOSED, {})
    hass.states.async_set(DEMO_TILT, CoverState.CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert ATTR_ASSUMED_STATE not in state.attributes

    # One member with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(DEMO_COVER, CoverState.OPEN, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Multiple members with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(
        DEMO_COVER_TILT, CoverState.CLOSED, {ATTR_ASSUMED_STATE: True}
    )
    hass.states.async_set(DEMO_TILT, CoverState.CLOSED, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Unavailable member with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(DEMO_COVER, CoverState.OPEN, {})
    hass.states.async_set(DEMO_COVER_TILT, CoverState.CLOSED, {})
    hass.states.async_set(DEMO_TILT, STATE_UNAVAILABLE, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # Unknown member with assumed_state=True -> group has assumed_state=True
    hass.states.async_set(DEMO_TILT, STATE_UNKNOWN, {ATTR_ASSUMED_STATE: True})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    # All members without assumed_state -> group doesn't have
    # assumed_state in attributes
    hass.states.async_set(DEMO_TILT, CoverState.CLOSED, {})
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert ATTR_ASSUMED_STATE not in state.attributes


async def test_nested_group(hass: HomeAssistant) -> None:
    """Test nested cover group."""
    await async_setup_component(
        hass,
        COVER_DOMAIN,
        {
            COVER_DOMAIN: [
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
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_ENTITY_ID) == [DEMO_COVER_POS, DEMO_COVER_TILT]

    state = hass.states.get("cover.nested_group")
    assert state is not None
    assert state.state == CoverState.OPEN
    assert state.attributes.get(ATTR_ENTITY_ID) == ["cover.bedroom_group"]

    # Test controlling the nested group
    async with asyncio.timeout(0.5):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.nested_group"},
            blocking=True,
        )
    assert hass.states.get(DEMO_COVER_POS).state == CoverState.CLOSING
    assert hass.states.get(DEMO_COVER_TILT).state == CoverState.CLOSING
    assert hass.states.get("cover.bedroom_group").state == CoverState.CLOSING
    assert hass.states.get("cover.nested_group").state == CoverState.CLOSING


@pytest.mark.parametrize("config_count", [(CONFIG_ATTRIBUTES, 1)])
@pytest.mark.usefixtures("setup_comp")
async def test_speeds(hass: HomeAssistant) -> None:
    """Test the group merges the speeds of its members."""
    speed_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SPEED
    )
    # A member with the speed feature but without speeds adds nothing
    hass.states.async_set(
        DEMO_TILT, CoverState.OPEN, {ATTR_SUPPORTED_FEATURES: speed_features}
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS not in state.attributes
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & CoverEntityFeature.SPEED

    # The speeds keep the order of the members
    hass.states.async_set(
        DEMO_COVER_TILT,
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: speed_features,
            CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS: ["silent", "fast"],
        },
    )
    hass.states.async_set(
        DEMO_COVER_POS,
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: speed_features,
            CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS: ["slow", "fast"],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.attributes[CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS] == [
        "slow",
        "fast",
        "silent",
    ]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & CoverEntityFeature.SPEED

    hass.states.async_set(
        DEMO_COVER_POS, CoverState.OPEN, {ATTR_SUPPORTED_FEATURES: 11}
    )
    # Core validates against the speeds even without the speed feature
    hass.states.async_set(
        DEMO_COVER,
        CoverState.OPEN,
        {
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
            CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS: ["quiet"],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert state.attributes[CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS] == [
        "quiet",
        "silent",
        "fast",
    ]

    hass.states.async_remove(DEMO_COVER)
    hass.states.async_remove(DEMO_COVER_TILT)
    await hass.async_block_till_done()

    state = hass.states.get(COVER_GROUP)
    assert CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS not in state.attributes
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & CoverEntityFeature.SPEED


@pytest.fixture
async def mock_speed_covers(hass: HomeAssistant) -> list[MockCover]:
    """Set up covers with different speeds and a group of them."""
    features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
    entities = [
        MockCover(
            name="Slow fast",
            unique_id="slow_fast",
            supported_features=features | CoverEntityFeature.SPEED,
            supported_speeds=["slow", "fast"],
            current_cover_position=50,
        ),
        MockCover(
            name="Silent fast",
            unique_id="silent_fast",
            supported_features=features | CoverEntityFeature.SPEED,
            supported_speeds=["silent", "fast"],
            current_cover_position=50,
        ),
        MockCover(
            name="No speed",
            unique_id="no_speed",
            supported_features=features,
            current_cover_position=50,
        ),
    ]
    setup_test_component_platform(hass, COVER_DOMAIN, entities)
    assert await async_setup_component(
        hass,
        COVER_DOMAIN,
        {
            COVER_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": "group",
                    CONF_ENTITIES: [SLOW_FAST_COVER, SILENT_FAST_COVER, NO_SPEED_COVER],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    return entities


@pytest.mark.parametrize(
    ("service", "data", "expected_kwargs"),
    [
        pytest.param(
            SERVICE_OPEN_COVER,
            {ATTR_SPEED: "fast"},
            [{ATTR_SPEED: "fast"}, {ATTR_SPEED: "fast"}, {}],
            id="open_speed_of_two_members",
        ),
        pytest.param(
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 30, ATTR_SPEED: "fast"},
            [
                {ATTR_POSITION: 30, ATTR_SPEED: "fast"},
                {ATTR_POSITION: 30, ATTR_SPEED: "fast"},
                {ATTR_POSITION: 30},
            ],
            id="set_position_speed_of_two_members",
        ),
        pytest.param(
            SERVICE_CLOSE_COVER,
            {ATTR_SPEED: "slow"},
            [{ATTR_SPEED: "slow"}, {}, {}],
            id="close_speed_of_one_member",
        ),
        pytest.param(
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 30, ATTR_SPEED: "silent"},
            [
                {ATTR_POSITION: 30},
                {ATTR_POSITION: 30, ATTR_SPEED: "silent"},
                {ATTR_POSITION: 30},
            ],
            id="set_position_speed_of_one_member",
        ),
        pytest.param(SERVICE_OPEN_COVER, {}, [{}, {}, {}], id="open_without_speed"),
        pytest.param(
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 30},
            [{ATTR_POSITION: 30}, {ATTR_POSITION: 30}, {ATTR_POSITION: 30}],
            id="set_position_without_speed",
        ),
    ],
)
async def test_speed_forwarded(
    hass: HomeAssistant,
    mock_speed_covers: list[MockCover],
    service: str,
    data: dict[str, Any],
    expected_kwargs: list[dict[str, Any]],
) -> None:
    """Test the speed is forwarded to the members that list it."""
    state = hass.states.get(COVER_GROUP)
    assert state.attributes[CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS] == [
        "slow",
        "fast",
        "silent",
    ]

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: COVER_GROUP, **data},
        blocking=True,
    )

    assert [entity.last_kwargs for entity in mock_speed_covers] == expected_kwargs


@pytest.mark.parametrize(
    "features",
    [
        pytest.param(
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE, id="with_action"
        ),
        pytest.param(CoverEntityFeature.OPEN, id="without_action"),
    ],
)
async def test_speed_unavailable_member(
    hass: HomeAssistant,
    mock_speed_covers: list[MockCover],
    features: CoverEntityFeature,
) -> None:
    """Test an unavailable member is not moved, with or without the action."""
    slow_fast, silent_fast, no_speed = mock_speed_covers
    silent_fast._values["available"] = False
    silent_fast._values["supported_features"] = features
    silent_fast.async_write_ha_state()
    await hass.async_block_till_done()
    assert hass.states.get(SILENT_FAST_COVER).state == STATE_UNAVAILABLE

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: COVER_GROUP, ATTR_SPEED: "slow"},
        blocking=True,
    )

    assert slow_fast.last_kwargs == {ATTR_SPEED: "slow"}
    assert silent_fast.last_kwargs is None
    assert no_speed.last_kwargs == {}


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="without_speed"),
        pytest.param({ATTR_SPEED: "fast"}, id="with_speed"),
        pytest.param({ATTR_SPEED: "slow"}, id="with_speed_of_member_without_action"),
    ],
)
async def test_speed_member_without_action(
    hass: HomeAssistant, data: dict[str, Any]
) -> None:
    """Test a member without the action is left to core, like without a speed."""
    entities = [
        MockCover(
            name="Open only",
            unique_id="open_only",
            supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.SPEED,
            supported_speeds=["slow"],
        ),
        MockCover(
            name="Open close",
            unique_id="open_close",
            supported_features=CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SPEED,
            supported_speeds=["fast"],
        ),
    ]
    setup_test_component_platform(hass, COVER_DOMAIN, entities)
    assert await async_setup_component(
        hass,
        COVER_DOMAIN,
        {
            COVER_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": "group",
                    CONF_ENTITIES: ["cover.open_only", "cover.open_close"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: COVER_GROUP, **data},
            blocking=True,
        )

    assert [entity.last_kwargs for entity in entities] == [None, None]


async def test_speed_not_supported_by_any_member(
    hass: HomeAssistant, mock_speed_covers: list[MockCover]
) -> None:
    """Test a speed no member supports is rejected."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: COVER_GROUP, ATTR_SPEED: "turbo"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "not_valid_speed"
    assert [entity.last_kwargs for entity in mock_speed_covers] == [None, None, None]


@pytest.mark.parametrize(
    ("failing", "error", "expected_kwargs"),
    [
        pytest.param(
            [SLOW_FAST_COVER], SLOW_FAST_COVER, [None, {}, {}], id="member_with_speed"
        ),
        pytest.param(
            [NO_SPEED_COVER],
            NO_SPEED_COVER,
            [{ATTR_SPEED: "slow"}, {}, None],
            id="member_without_speed",
        ),
        pytest.param(
            [SLOW_FAST_COVER, NO_SPEED_COVER],
            NO_SPEED_COVER,
            [None, {}, None],
            id="members_of_both_calls",
        ),
    ],
)
async def test_speed_member_failure(
    hass: HomeAssistant,
    mock_speed_covers: list[MockCover],
    failing: list[str],
    error: str,
    expected_kwargs: list[dict[str, Any] | None],
) -> None:
    """Test all members are called before the first member error is raised."""
    covers = {cover.entity_id: cover for cover in mock_speed_covers}
    with ExitStack() as stack:
        for entity_id in failing:
            stack.enter_context(
                patch.object(
                    covers[entity_id],
                    "async_open_cover",
                    side_effect=HomeAssistantError(entity_id),
                )
            )
        # The call without the speed comes first in the call order
        with pytest.raises(HomeAssistantError, match=error):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_OPEN_COVER,
                {ATTR_ENTITY_ID: COVER_GROUP, ATTR_SPEED: "slow"},
                blocking=True,
            )

    assert [entity.last_kwargs for entity in mock_speed_covers] == expected_kwargs


async def test_speed_member_not_delayed(
    hass: HomeAssistant, mock_speed_covers: list[MockCover]
) -> None:
    """Test a member that takes long does not delay the members with the speed."""
    slow_fast, _, no_speed = mock_speed_covers
    release = asyncio.Event()

    async def slow_open_cover(**kwargs: Any) -> None:
        await release.wait()
        no_speed.last_kwargs = kwargs

    with (
        patch.object(slow_fast, "async_open_cover") as open_with_speed,
        patch.object(no_speed, "async_open_cover", side_effect=slow_open_cover),
    ):
        call = hass.async_create_task(
            hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_OPEN_COVER,
                {ATTR_ENTITY_ID: COVER_GROUP, ATTR_SPEED: "slow"},
                blocking=True,
            )
        )
        for _ in range(10):
            await asyncio.sleep(0)

        open_with_speed.assert_awaited_once_with(speed="slow")
        assert not call.done()

        release.set()
        await call

    assert no_speed.last_kwargs == {}


@pytest.mark.parametrize(
    ("data", "fast_kwargs"),
    [
        pytest.param({}, {}, id="without_speed"),
        pytest.param({ATTR_SPEED: "fast"}, {ATTR_SPEED: "fast"}, id="with_speed"),
    ],
)
async def test_nested_group_member_without_action(
    hass: HomeAssistant, data: dict[str, Any], fast_kwargs: dict[str, Any]
) -> None:
    """Test the other members move when a nested group rejects the action."""
    features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.SPEED
    )
    entities = [
        MockCover(
            name="Open only",
            unique_id="open_only",
            supported_features=CoverEntityFeature.OPEN,
        ),
        MockCover(
            name="Slow",
            unique_id="slow",
            supported_features=features,
            supported_speeds=["slow"],
        ),
        MockCover(
            name="Fast",
            unique_id="fast",
            supported_features=features,
            supported_speeds=["fast"],
        ),
        MockCover(
            name="No speed",
            unique_id="no_speed",
            supported_features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
        ),
    ]
    setup_test_component_platform(hass, COVER_DOMAIN, entities)
    assert await async_setup_component(
        hass,
        COVER_DOMAIN,
        {
            COVER_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": "group",
                    CONF_ENTITIES: ["cover.inner_group", "cover.fast", NO_SPEED_COVER],
                    "name": "Outer Group",
                },
                {
                    "platform": "group",
                    CONF_ENTITIES: ["cover.open_only", "cover.slow"],
                    "name": "Inner Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # Core rejects the member of the nested group after the call reached it
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: OUTER_GROUP, **data},
            blocking=True,
        )

    assert [entity.last_kwargs for entity in entities] == [None, None, fast_kwargs, {}]


async def test_nested_group_speed(hass: HomeAssistant) -> None:
    """Test a nested group forwards the speed."""
    entity = MockCover(
        name="Slow fast",
        unique_id="slow_fast",
        supported_features=CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SPEED,
        supported_speeds=["slow", "fast"],
    )
    setup_test_component_platform(hass, COVER_DOMAIN, [entity])
    assert await async_setup_component(
        hass,
        COVER_DOMAIN,
        {
            COVER_DOMAIN: [
                {"platform": "test"},
                {
                    "platform": "group",
                    CONF_ENTITIES: ["cover.inner_group"],
                    "name": "Outer Group",
                },
                {
                    "platform": "group",
                    CONF_ENTITIES: [SLOW_FAST_COVER],
                    "name": "Inner Group",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get(OUTER_GROUP)
    assert state.attributes[CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS] == [
        "slow",
        "fast",
    ]

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: OUTER_GROUP, ATTR_SPEED: "slow"},
        blocking=True,
    )

    assert entity.last_kwargs == {ATTR_SPEED: "slow"}
