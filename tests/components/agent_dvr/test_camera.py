"""Tests for the Agent DVR camera platform."""

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_camera_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a camera entity is created from getObjects and reflects its state.

    MjpegCamera's __init__ sets its own _attr_name from the `name=` kwarg,
    which overrides the class-level `_attr_name = None` this entity sets
    for a has_entity_name-only display name. The result is the device name
    and entity name both being "Front Door", hence the doubled entity_id -
    this is pre-existing camera.py/MjpegCamera behavior, not something
    introduced here.
    """
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("camera.desktop_front_door_front_door")
    assert state is not None
    assert state.state == "idle"
    assert state.attributes["location"] == "Front Yard"
    assert state.attributes["groups"] == "outside"
    assert state.attributes["ptz_type"] == "ONVIF"
    assert state.attributes["has_ptz"] is True
