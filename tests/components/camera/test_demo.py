"""The tests for local file camera component."""
import asyncio
from homeassistant.components import camera
from homeassistant.setup import async_setup_component


@asyncio.coroutine
def test_motion_detection(hass):
    """Test motion detection services."""
    # Setup platform
    yield from async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'demo'
        }
    })

    # Fetch state and check motion detection attribute
    state = hass.states.get('camera.demo_camera')
    assert not state.attributes.get('motion_detection')

    # Call service to turn on motion detection
    camera.enable_motion_detection(hass, 'camera.demo_camera')
    yield from hass.async_block_till_done()

    # Check if state has been updated.
    state = hass.states.get('camera.demo_camera')
    assert state.attributes.get('motion_detection')
