"""The tests for the kitchen_sink lawn mower platform."""
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events, async_mock_service

MOWER_SERVICE_ENTITY = "lawn_mower.mower_can_dock"


@pytest.fixture
async def lawn_mower_only() -> None:
    """Enable only the lawn mower platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.LAWN_MOWER],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, lawn_mower_only):
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the expected lawn mower entities are added."""
    states = hass.states.async_all()
    assert set(states) == snapshot


@pytest.mark.parametrize(
    ("entity", "service_call", "activity", "next_activity"),
    [
        (
            "lawn_mower.mower_can_mow",
            SERVICE_START_MOWING,
            LawnMowerActivity.DOCKED,
            LawnMowerActivity.MOWING,
        ),
        (
            "lawn_mower.mower_can_pause",
            SERVICE_PAUSE,
            LawnMowerActivity.DOCKING,
            LawnMowerActivity.PAUSED,
        ),
        (
            "lawn_mower.mower_is_paused",
            SERVICE_START_MOWING,
            LawnMowerActivity.PAUSED,
            LawnMowerActivity.MOWING,
        ),
        (
            "lawn_mower.mower_can_dock",
            SERVICE_DOCK,
            LawnMowerActivity.MOWING,
            LawnMowerActivity.DOCKING,
        ),
    ],
)
async def test_mower(
    hass: HomeAssistant,
    entity: str,
    service_call: str,
    activity: LawnMowerActivity,
    next_activity: LawnMowerActivity,
) -> None:
    """Test the activity states of a lawn mower."""
    state = hass.states.get(entity)

    assert state.state == str(activity.value)
    await hass.async_block_till_done()

    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.services.async_call(
        LAWN_MOWER_DOMAIN, service_call, {ATTR_ENTITY_ID: entity}, blocking=False
    )
    await hass.async_block_till_done()

    assert state_changes[0].data["entity_id"] == entity
    assert state_changes[0].data["new_state"].state == str(next_activity.value)


@pytest.mark.parametrize(
    "service_call",
    [
        SERVICE_DOCK,
        SERVICE_START_MOWING,
        SERVICE_PAUSE,
    ],
)
async def test_service_calls_mocked(hass: HomeAssistant, service_call) -> None:
    """Test the services of a lawn mower."""
    calls = async_mock_service(hass, LAWN_MOWER_DOMAIN, service_call)
    await hass.services.async_call(
        LAWN_MOWER_DOMAIN,
        service_call,
        {ATTR_ENTITY_ID: MOWER_SERVICE_ENTITY},
        blocking=True,
    )
    assert len(calls) == 1
