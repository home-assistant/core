"""The tests for local file camera component."""
import asyncio
from unittest.mock import mock_open, patch

from homeassistant.components import camera, http
from homeassistant.components.camera import STATE_STREAMING, STATE_IDLE
from homeassistant.setup import async_setup_component, setup_component
from tests.common import get_test_home_assistant, get_test_instance_port


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


class TestTurnOnOffDemoCamera(object):
    """Test class for camera."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        setup_component(
            self.hass, http.DOMAIN,
            {http.DOMAIN: {http.CONF_SERVER_PORT: get_test_instance_port()}})

        config = {
            camera.DOMAIN: {
                'platform': 'demo'
            }
        }

        setup_component(self.hass, camera.DOMAIN, config)

        self.hass.start()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_init_state_is_streaming(self):
        """Demo camera initialize as streaming."""
        state = self.hass.states.get('camera.demo_camera')
        assert state.state == STATE_STREAMING

        mock_on_img = mock_open(read_data=b'ON')
        with patch('homeassistant.components.camera.demo.open', mock_on_img,
                   create=True):
            image = asyncio.run_coroutine_threadsafe(camera.async_get_image(
                self.hass, 'camera.demo_camera'), self.hass.loop).result()
            assert mock_on_img.called
            assert mock_on_img.call_args_list[0][0][0][-6:]\
                in ['_0.jpg', '_1.jpg', '_2.jpg', '_3.jpg']
            assert image.content == b'ON'

    def test_turn_off_image(self):
        """After turn off, Demo camera return off image."""
        camera.turn_off(self.hass, 'camera.demo_camera')
        self.hass.block_till_done()

        mock_off_img = mock_open(read_data=b'OFF')
        with patch('homeassistant.components.camera.demo.open', mock_off_img,
                   create=True):
            image = asyncio.run_coroutine_threadsafe(camera.async_get_image(
                self.hass, 'camera.demo_camera'), self.hass.loop).result()
            assert mock_off_img.called
            assert mock_off_img.call_args_list[0][0][0][-8:] == '_off.jpg'
            assert image.content == b'OFF'

    def test_turn_on_state_back_to_streaming(self):
        """After turn on state back to streaming"""
        camera.turn_off(self.hass, 'camera.demo_camera')
        self.hass.block_till_done()

        state = self.hass.states.get('camera.demo_camera')
        assert state.state == STATE_IDLE

        camera.turn_on(self.hass, 'camera.demo_camera')
        self.hass.block_till_done()

        state = self.hass.states.get('camera.demo_camera')
        assert state.state == STATE_STREAMING

    def test_turn_off_invalid_camera(self):
        """Turn off non-exist camera should quietly fail."""

        camera.turn_off(self.hass, 'camera.demo_camera_1')
        self.hass.block_till_done()

        state = self.hass.states.get('camera.demo_camera')
        assert state.state == STATE_STREAMING
