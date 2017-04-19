"""The tests for mqtt camera component."""
import asyncio
import unittest

from homeassistant.setup import async_setup_component

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, get_test_instance_port)

import requests

SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = 'http://127.0.0.1:{}'.format(SERVER_PORT)


class TestComponentsMQTTCamera(unittest.TestCase):
    """Test MQTT camera platform."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_mqtt = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @asyncio.coroutine
    def test_run_camera_setup(self):
        """Test that it fetches the given payload."""
        topic = 'test/camera'
        yield from async_setup_component(self.hass, 'camera', {
            'camera': {
                'platform': 'mqtt',
                'topic': topic,
                'name': 'Test Camera',
            }})

        self.mock_mqtt.publish(self.hass, topic, 0xFFD8FF)
        yield from self.hass.async_block_till_done()

        resp = requests.get(HTTP_BASE_URL +
                            '/api/camera_proxy/camera.test_camera')

        assert resp.status_code == 200
        body = yield from resp.text
        assert body == '16767231'
