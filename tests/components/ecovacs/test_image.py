"""Tests for Ecovacs image entities."""

from deebot_client.events.map import MapTraceEvent
import pytest

from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.IMAGE


_ENTITY_ID = "image.goat_g1_trace_map"


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_created(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """A mower device exposes a trace_map image entity in the unknown state."""
    assert (state := hass.states.get(_ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_state_advances_after_trace_event(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """After a MapTraceEvent the entity state advances away from ``unknown``."""
    device = controller.devices[0]
    pre = hass.states.get(_ENTITY_ID)
    assert pre is not None
    assert pre.state == STATE_UNKNOWN

    await notify_and_wait(
        hass,
        device.events,
        MapTraceEvent(start=1, total=1, data="0,0;100,200;200,400;300,600"),
    )

    post = hass.states.get(_ENTITY_ID)
    assert post is not None
    assert post.state != STATE_UNKNOWN


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_state_changes_on_each_event(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Successive ``MapTraceEvent``s update the state timestamp each time."""
    device = controller.devices[0]
    timestamps: list[str] = []
    for chunk in ("0,0;100,100", "200,200;300,300", "400,400;500,500"):
        await notify_and_wait(
            hass,
            device.events,
            MapTraceEvent(start=1, total=1, data=chunk),
        )
        state = hass.states.get(_ENTITY_ID)
        assert state is not None
        timestamps.append(state.state)

    # Each trace event must produce a strictly later timestamp.
    assert timestamps == sorted(set(timestamps))
    assert len(timestamps) == 3


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_ignores_malformed_tokens(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Empty segments and the leading "0" anchor must not crash the renderer."""
    device = controller.devices[0]
    await notify_and_wait(
        hass,
        device.events,
        MapTraceEvent(start=1, total=1, data="0;;100,200;not-a-pair;300,400;"),
    )

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNKNOWN
