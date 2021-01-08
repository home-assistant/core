"""The tests for the Demo cover platform."""
from datetime import timedelta

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
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
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

CONFIG = {"cover": {"platform": "demo"}}
ENTITY_COVER = "cover.living_room_window"


@pytest.fixture
async def setup_comp(hass):
    """Set up demo cover component."""
    with assert_setup_component(1, DOMAIN):
        await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()


async def test_supported_features(hass, setup_comp):
    """Test cover supported features."""
    state = hass.states.get("cover.garage_door")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 3
    state = hass.states.get("cover.kitchen_window")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 11
    state = hass.states.get("cover.hall_window")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 15
    state = hass.states.get("cover.living_room_window")
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 255


async def test_close_cover(hass, setup_comp):
    """Test closing the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 70

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_CLOSING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_open_cover(hass, setup_comp):
    """Test opening the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_OPENING
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_toggle_cover(hass, setup_comp):
    """Test toggling the cover."""
    # Start open
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 100
    # Toggle closed
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    # Toggle open
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == STATE_OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 100


async def test_set_cover_position(hass, setup_comp):
    """Test moving the cover to a specific position."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 10},
        blocking=True,
    )
    for _ in range(6):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 10


async def test_stop_cover(hass, setup_comp):
    """Test stopping the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 70
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_POSITION] == 80


async def test_close_cover_tilt(hass, setup_comp):
    """Test closing the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


async def test_open_cover_tilt(hass, setup_comp):
    """Test opening the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_toggle_cover_tilt(hass, setup_comp):
    """Test toggling the cover tilt."""
    # Start open
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100
    # Toggle closed
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0
    # Toggle Open
    await hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    for _ in range(10):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_set_cover_tilt_position(hass, setup_comp):
    """Test moving the cover til to a specific position."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 90},
        blocking=True,
    )
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 90


async def test_stop_cover_tilt(hass, setup_comp):
    """Test stopping the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER_TILT, {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True
    )
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_COVER)
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 40
