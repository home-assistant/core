"""The tests for generic camera component."""
import asyncio
from unittest import mock

from homeassistant.bootstrap import (async_setup_component, setup_component)
from homeassistant.const import (ATTR_ENTITY_ID, CONF_NAME, CONF_PLATFORM)
import homeassistant.components.camera as camera
from tests.common import assert_setup_component


@asyncio.coroutine
def test_fetching_url(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    aioclient_mock.get('http://example.com', text='hello world')

    def setup_platform():
        """Setup the platform."""
        assert setup_component(hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'generic',
                'still_image_url': 'http://example.com',
                'username': 'user',
                'password': 'pass'
            }})

    yield from hass.loop.run_in_executor(None, setup_platform)

    client = yield from test_client(hass.http.app)

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = yield from resp.text()
    assert body == 'hello world'

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2


@asyncio.coroutine
def test_limit_refetch(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    aioclient_mock.get('http://example.com/5a', text='hello world')
    aioclient_mock.get('http://example.com/10a', text='hello world')
    aioclient_mock.get('http://example.com/15a', text='hello planet')
    aioclient_mock.get('http://example.com/20a', status=404)

    def setup_platform():
        """Setup the platform."""
        assert setup_component(hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'generic',
                'still_image_url':
                'http://example.com/{{ states.sensor.temp.state + "a" }}',
                'limit_refetch_to_url_change': True,
            }})

    yield from hass.loop.run_in_executor(None, setup_platform)

    client = yield from test_client(hass.http.app)

    resp = yield from client.get('/api/camera_proxy/camera.config_test')

    hass.states.async_set('sensor.temp', '5')

    with mock.patch('async_timeout.timeout',
                    side_effect=asyncio.TimeoutError()):
        resp = yield from client.get('/api/camera_proxy/camera.config_test')
        assert aioclient_mock.call_count == 0
        assert resp.status == 500

    hass.states.async_set('sensor.temp', '10')

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello world'

    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 1
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello world'

    hass.states.async_set('sensor.temp', '15')

    # Url change = fetch new image
    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello planet'

    # Cause a template render error
    hass.states.async_remove('sensor.temp')
    resp = yield from client.get('/api/camera_proxy/camera.config_test')
    assert aioclient_mock.call_count == 2
    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello planet'


@asyncio.coroutine
def test_setup_component(aioclient_mock, hass, test_client):
    """Test that setup register service."""
    config = {
        camera.DOMAIN: {
            CONF_PLATFORM: 'generic',
            'still_image_url': 'http://example.com',
        }
    }
    with assert_setup_component(1, camera.DOMAIN):
        assert(yield from async_setup_component(hass, camera.DOMAIN, config))
    assert hass.services.has_service(
        camera.DOMAIN, camera.SERVICE_UPDATE_IMAGE)


@asyncio.coroutine
def test_call_service(aioclient_mock, hass, test_client):
    """Test that update_image service call causes data image refetch."""
    aioclient_mock.get('http://example.com', text='hello world')
    name = 'test_camera'

    config = {
        camera.DOMAIN: {
            CONF_NAME: name,
            CONF_PLATFORM: 'generic',
            'still_image_url': 'http://example.com',
        }
    }
    with assert_setup_component(1, camera.DOMAIN):
        assert(yield from async_setup_component(hass, camera.DOMAIN, config))
    assert aioclient_mock.call_count == 0

    yield from hass.services.async_call(
        camera.DOMAIN,
        camera.SERVICE_UPDATE_IMAGE,
        {ATTR_ENTITY_ID: "{}.{}".format(camera.DOMAIN, name)})

    yield from hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
