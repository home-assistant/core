"""The tests for local file camera component."""
import pytest

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_STREAMING,
    async_get_image,
)
from homeassistant.components.demo import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.async_mock import patch

ENTITY_CAMERA = "camera.demo_camera"


@pytest.fixture(autouse=True)
def demo_camera(hass):
    """Initialize a demo camera platform."""
    hass.loop.run_until_complete(
        async_setup_component(
            hass, CAMERA_DOMAIN, {CAMERA_DOMAIN: {"platform": DOMAIN}}
        )
    )


async def test_init_state_is_streaming(hass):
    """Demo camera initialize as streaming."""
    state = hass.states.get(ENTITY_CAMERA)
    assert state.state == STATE_STREAMING

    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes", return_value=b"ON"
    ) as mock_read_bytes:
        image = await async_get_image(hass, ENTITY_CAMERA)
        assert mock_read_bytes.call_count == 1
        assert image.content == b"ON"


async def test_turn_on_state_back_to_streaming(hass):
    """After turn on state back to streaming."""
    state = hass.states.get(ENTITY_CAMERA)
    assert state.state == STATE_STREAMING

    await hass.services.async_call(
        CAMERA_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_CAMERA}, blocking=True
    )

    state = hass.states.get(ENTITY_CAMERA)
    assert state.state == STATE_IDLE

    await hass.services.async_call(
        CAMERA_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_CAMERA}, blocking=True
    )

    state = hass.states.get(ENTITY_CAMERA)
    assert state.state == STATE_STREAMING


async def test_turn_off_image(hass):
    """After turn off, Demo camera raise error."""
    await hass.services.async_call(
        CAMERA_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_CAMERA}, blocking=True
    )

    with pytest.raises(HomeAssistantError) as error:
        await async_get_image(hass, ENTITY_CAMERA)
        assert error.args[0] == "Camera is off"


async def test_turn_off_invalid_camera(hass):
    """Turn off non-exist camera should quietly fail."""
    state = hass.states.get(ENTITY_CAMERA)
    assert state.state == STATE_STREAMING

    await hass.services.async_call(
        CAMERA_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "camera.invalid_camera"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_CAMERA)
    assert state.state == STATE_STREAMING


async def test_motion_detection(hass):
    """Test motion detection services."""

    # Fetch state and check motion detection attribute
    state = hass.states.get(ENTITY_CAMERA)
    assert not state.attributes.get("motion_detection")

    # Call service to turn on motion detection
    await hass.services.async_call(
        CAMERA_DOMAIN,
        SERVICE_ENABLE_MOTION,
        {ATTR_ENTITY_ID: ENTITY_CAMERA},
        blocking=True,
    )

    # Check if state has been updated.
    state = hass.states.get(ENTITY_CAMERA)
    assert state.attributes.get("motion_detection")

    # Call service to turn off motion detection
    await hass.services.async_call(
        CAMERA_DOMAIN,
        SERVICE_DISABLE_MOTION,
        {ATTR_ENTITY_ID: ENTITY_CAMERA},
        blocking=True,
    )

    # Check if state has been updated.
    state = hass.states.get(ENTITY_CAMERA)
    assert not state.attributes.get("motion_detection")
