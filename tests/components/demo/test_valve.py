"""The tests for the Demo valve platform."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.demo import DOMAIN, valve as demo_valve
from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    ValveState,
)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_capture_events, async_fire_time_changed

FRONT_GARDEN = "valve.front_garden"
ORCHARD = "valve.orchard"
BACK_GARDEN = "valve.back_garden"


@pytest.fixture
async def valve_only() -> None:
    """Enable only the valve platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.VALVE],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, valve_only: None):
    """Set up demo component."""
    assert await async_setup_component(
        hass, VALVE_DOMAIN, {VALVE_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()


@patch.object(demo_valve, "OPEN_CLOSE_DELAY", 0)
async def test_closing(hass: HomeAssistant) -> None:
    """Test the closing of a valve."""
    state = hass.states.get(FRONT_GARDEN)
    assert state.state == ValveState.OPEN
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: FRONT_GARDEN},
        blocking=False,
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == FRONT_GARDEN
    assert state_changes[0].data["new_state"].state == ValveState.CLOSING

    assert state_changes[1].data["entity_id"] == FRONT_GARDEN
    assert state_changes[1].data["new_state"].state == ValveState.CLOSED


@patch.object(demo_valve, "OPEN_CLOSE_DELAY", 0)
async def test_opening(hass: HomeAssistant) -> None:
    """Test the opening of a valve."""
    state = hass.states.get(ORCHARD)
    assert state.state == ValveState.CLOSED
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {ATTR_ENTITY_ID: ORCHARD}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == ORCHARD
    assert state_changes[0].data["new_state"].state == ValveState.OPENING

    assert state_changes[1].data["entity_id"] == ORCHARD
    assert state_changes[1].data["new_state"].state == ValveState.OPEN


async def test_set_valve_position(hass: HomeAssistant) -> None:
    """Test moving the valve to a specific position."""
    state = hass.states.get(BACK_GARDEN)
    assert state.attributes[ATTR_CURRENT_POSITION] == 70

    # close to 10%
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: BACK_GARDEN, ATTR_POSITION: 10},
        blocking=True,
    )
    state = hass.states.get(BACK_GARDEN)
    assert state.state == ValveState.CLOSING

    for _ in range(6):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(BACK_GARDEN)
    assert state.attributes[ATTR_CURRENT_POSITION] == 10
    assert state.state == ValveState.OPEN

    # open to 80%
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: BACK_GARDEN, ATTR_POSITION: 80},
        blocking=True,
    )
    state = hass.states.get(BACK_GARDEN)
    assert state.state == ValveState.OPENING

    for _ in range(7):
        future = dt_util.utcnow() + timedelta(seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get(BACK_GARDEN)
    assert state.attributes[ATTR_CURRENT_POSITION] == 80
    assert state.state == ValveState.OPEN

    # test valve is at requested position
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: BACK_GARDEN, ATTR_POSITION: 80},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(state_changes) == 0
