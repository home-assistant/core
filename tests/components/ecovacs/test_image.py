"""Tests for Ecovacs image entities."""

from deebot_client.events.map import MapTraceEvent
import pytest

from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.IMAGE


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_created(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """A mower device exposes a trace_map image entity."""
    entity_id = "image.goat_g1_trace_map"
    assert (state := hass.states.get(entity_id))
    assert state.attributes["content_type"] == "image/svg+xml"


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_renders_svg_after_trace_event(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """After a MapTraceEvent the entity exposes a non-empty SVG."""
    entity_id = "image.goat_g1_trace_map"
    device = controller.devices[0]

    await notify_and_wait(
        hass,
        device.events,
        MapTraceEvent(start=1, total=1, data="0,0;100,200;200,400;300,600"),
    )

    image_state = hass.states.get(entity_id)
    assert image_state is not None
    assert image_state.attributes["content_type"] == "image/svg+xml"


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_accumulates_points_across_events(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Successive MapTraceEvents add to the running trace."""
    device = controller.devices[0]

    for chunk in ("0,0;100,100", "200,200;300,300", "400,400;500,500"):
        await notify_and_wait(
            hass,
            device.events,
            MapTraceEvent(start=1, total=1, data=chunk),
        )

    image_state = hass.states.get("image.goat_g1_trace_map")
    assert image_state is not None
    # ``last_updated`` advances with each notification
    assert image_state.attributes["content_type"] == "image/svg+xml"


@pytest.mark.parametrize(("device_fixture"), ["5xu9h3"])
async def test_mower_trace_map_ignores_empty_or_malformed_tokens(
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

    image_state = hass.states.get("image.goat_g1_trace_map")
    assert image_state is not None
