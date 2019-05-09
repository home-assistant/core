"""The tests for the Demo cover platform."""
from datetime import timedelta

import pytest

from homeassistant.components.cover import (
    ATTR_POSITION, ATTR_TILT_POSITION, DOMAIN)
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_CLOSE_COVER, SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER, SERVICE_OPEN_COVER_TILT, SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION, SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

CONFIG = {'cover': {'platform': 'demo'}}
ENTITY_COVER = 'cover.living_room_window'


@pytest.fixture
async def setup_comp(hass):
    """Set up demo cover component."""
    with assert_setup_component(1, DOMAIN):
        await async_setup_component(hass, DOMAIN, CONFIG)


async def test_supported_features(hass, setup_comp):
    """Test cover supported features."""
    state = hass.states.get('cover.garage_door')
    assert 3 == state.attributes.get('supported_features')
    state = hass.states.get('cover.kitchen_window')
    assert 11 == state.attributes.get('supported_features')
    state = hass.states.get('cover.hall_window')
    assert 15 == state.attributes.get('supported_features')
    state = hass.states.get('cover.living_room_window')
    assert 255 == state.attributes.get('supported_features')


async def test_close_cover(hass, setup_comp):
    """Test closing the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.state == 'open'
    assert 70 == state.attributes.get('current_position')

    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    state = hass.states.get(ENTITY_COVER)
    assert state.state == 'closing'
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == 'closed'
    assert 0 == state.attributes.get('current_position')


async def test_open_cover(hass, setup_comp):
    """Test opening the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert state.state == 'open'
    assert 70 == state.attributes.get('current_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    state = hass.states.get(ENTITY_COVER)
    assert state.state == 'opening'
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert state.state == 'open'
    assert 100 == state.attributes.get('current_position')


async def test_set_cover_position(hass, setup_comp):
    """Test moving the cover to a specific position."""
    state = hass.states.get(ENTITY_COVER)
    assert 70 == state.attributes.get('current_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_POSITION: 10}, blocking=True)
    for _ in range(6):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert 10 == state.attributes.get('current_position')


async def test_stop_cover(hass, setup_comp):
    """Test stopping the cover."""
    state = hass.states.get(ENTITY_COVER)
    assert 70 == state.attributes.get('current_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_COVER)
    assert 80 == state.attributes.get('current_position')


async def test_close_cover_tilt(hass, setup_comp):
    """Test closing the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert 50 == state.attributes.get('current_tilt_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert 0 == state.attributes.get('current_tilt_position')


async def test_open_cover_tilt(hass, setup_comp):
    """Test opening the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert 50 == state.attributes.get('current_tilt_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert 100 == state.attributes.get('current_tilt_position')


async def test_set_cover_tilt_position(hass, setup_comp):
    """Test moving the cover til to a specific position."""
    state = hass.states.get(ENTITY_COVER)
    assert 50 == state.attributes.get('current_tilt_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: ENTITY_COVER, ATTR_TILT_POSITION: 90}, blocking=True)
    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_COVER)
    assert 90 == state.attributes.get('current_tilt_position')


async def test_stop_cover_tilt(hass, setup_comp):
    """Test stopping the cover tilt."""
    state = hass.states.get(ENTITY_COVER)
    assert 50 == state.attributes.get('current_tilt_position')
    await hass.services.async_call(
        DOMAIN, SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: ENTITY_COVER}, blocking=True)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_COVER)
    assert 40 == state.attributes.get('current_tilt_position')
