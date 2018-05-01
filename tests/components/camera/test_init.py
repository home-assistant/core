"""The tests for the camera component."""
import asyncio
import base64
from unittest.mock import patch, mock_open

import pytest

from homeassistant.setup import setup_component, async_setup_component
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.components import camera, http, websocket_api
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.async_ import run_coroutine_threadsafe

from tests.common import (
    get_test_home_assistant, get_test_instance_port, assert_setup_component,
    mock_coro)


@pytest.fixture
def mock_camera(hass):
    """Initialize a demo camera platform."""
    assert hass.loop.run_until_complete(async_setup_component(hass, 'camera', {
        camera.DOMAIN: {
            'platform': 'demo'
        }
    }))

    with patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
               return_value=b'Test'):
        yield


class TestSetupCamera(object):
    """Test class for setup camera."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Setup demo platform on camera component."""
        config = {
            camera.DOMAIN: {
                'platform': 'demo'
            }
        }

        with assert_setup_component(1, camera.DOMAIN):
            setup_component(self.hass, camera.DOMAIN, config)


class TestGetImage(object):
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

        state = self.hass.states.get('camera.demo_camera')
        self.url = "{0}{1}".format(
            self.hass.config.api.base_url,
            state.attributes.get(ATTR_ENTITY_PICTURE))

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
           autospec=True, return_value=b'Test')
    def test_get_image_from_camera(self, mock_camera):
        """Grab an image from camera entity."""
        self.hass.start()

        image = run_coroutine_threadsafe(camera.async_get_image(
            self.hass, 'camera.demo_camera'), self.hass.loop).result()

        assert mock_camera.called
        assert image.content == b'Test'

    def test_get_image_without_exists_camera(self):
        """Try to get image without exists camera."""
        with patch('homeassistant.helpers.entity_component.EntityComponent.'
                   'get_entity', return_value=None), \
                pytest.raises(HomeAssistantError):
            run_coroutine_threadsafe(camera.async_get_image(
                self.hass, 'camera.demo_camera'), self.hass.loop).result()

    def test_get_image_with_timeout(self):
        """Try to get image with timeout."""
        with patch('homeassistant.components.camera.Camera.async_camera_image',
                   side_effect=asyncio.TimeoutError), \
                pytest.raises(HomeAssistantError):
            run_coroutine_threadsafe(camera.async_get_image(
                self.hass, 'camera.demo_camera'), self.hass.loop).result()

    def test_get_image_fails(self):
        """Try to get image with timeout."""
        with patch('homeassistant.components.camera.Camera.async_camera_image',
                   return_value=mock_coro(None)), \
                pytest.raises(HomeAssistantError):
            run_coroutine_threadsafe(camera.async_get_image(
                self.hass, 'camera.demo_camera'), self.hass.loop).result()


@asyncio.coroutine
def test_snapshot_service(hass, mock_camera):
    """Test snapshot service."""
    mopen = mock_open()

    with patch('homeassistant.components.camera.open', mopen, create=True), \
            patch.object(hass.config, 'is_allowed_path',
                         return_value=True):
        hass.components.camera.async_snapshot('/tmp/bla')
        yield from hass.async_block_till_done()

        mock_write = mopen().write

        assert len(mock_write.mock_calls) == 1
        assert mock_write.mock_calls[0][1][0] == b'Test'


async def test_webocket_camera_thumbnail(hass, hass_ws_client, mock_camera):
    """Test camera_thumbnail websocket command."""
    await async_setup_component(hass, 'camera')

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'camera_thumbnail',
        'entity_id': 'camera.demo_camera',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == websocket_api.TYPE_RESULT
    assert msg['success']
    assert msg['result']['content_type'] == 'image/jpeg'
    assert msg['result']['content'] == \
        base64.b64encode(b'Test').decode('utf-8')
