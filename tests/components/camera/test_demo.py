"""The tests for local file camera component."""
from unittest.mock import mock_open, patch

import pytest

from homeassistant.components import camera
from homeassistant.components.camera import STATE_STREAMING, STATE_IDLE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.components.camera import common


@pytest.fixture
def demo_camera(hass):
    """Initialize a demo camera platform."""
    hass.loop.run_until_complete(async_setup_component(hass, 'camera', {
        camera.DOMAIN: {
            'platform': 'demo'
        }
    }))
    return hass.data['camera'].get_entity('camera.demo_camera')


async def test_init_state_is_streaming(hass, demo_camera):
    """Demo camera initialize as streaming."""
    assert demo_camera.state == STATE_STREAMING

    mock_on_img = mock_open(read_data=b'ON')
    with patch('homeassistant.components.camera.demo.open', mock_on_img,
               create=True):
        image = await camera.async_get_image(hass, demo_camera.entity_id)
        assert mock_on_img.called
        assert mock_on_img.call_args_list[0][0][0][-6:] \
            in ['_0.jpg', '_1.jpg', '_2.jpg', '_3.jpg']
        assert image.content == b'ON'


async def test_turn_on_state_back_to_streaming(hass, demo_camera):
    """After turn on state back to streaming."""
    assert demo_camera.state == STATE_STREAMING
    await common.async_turn_off(hass, demo_camera.entity_id)
    await hass.async_block_till_done()

    assert demo_camera.state == STATE_IDLE

    await common.async_turn_on(hass, demo_camera.entity_id)
    await hass.async_block_till_done()

    assert demo_camera.state == STATE_STREAMING


async def test_turn_off_image(hass, demo_camera):
    """After turn off, Demo camera raise error."""
    await common.async_turn_off(hass, demo_camera.entity_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as error:
        await camera.async_get_image(hass, demo_camera.entity_id)
        assert error.args[0] == 'Camera is off'


async def test_turn_off_invalid_camera(hass, demo_camera):
    """Turn off non-exist camera should quietly fail."""
    assert demo_camera.state == STATE_STREAMING
    await common.async_turn_off(hass, 'camera.invalid_camera')
    await hass.async_block_till_done()

    assert demo_camera.state == STATE_STREAMING


async def test_motion_detection(hass):
    """Test motion detection services."""
    # Setup platform
    await async_setup_component(hass, 'camera', {
        'camera': {
            'platform': 'demo'
        }
    })

    # Fetch state and check motion detection attribute
    state = hass.states.get('camera.demo_camera')
    assert not state.attributes.get('motion_detection')

    # Call service to turn on motion detection
    common.enable_motion_detection(hass, 'camera.demo_camera')
    await hass.async_block_till_done()

    # Check if state has been updated.
    state = hass.states.get('camera.demo_camera')
    assert state.attributes.get('motion_detection')
