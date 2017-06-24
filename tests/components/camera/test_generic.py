"""The tests for generic camera component."""
import asyncio
from unittest import mock

from homeassistant.setup import setup_component


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
def test_camera_content_type(aioclient_mock, hass, test_client):
    """Test generic camera with custom content_type."""
    svg_image = '''<?xml version="1.0"?>
    <svg xmlns="http://www.w3.org/2000/svg"
    xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="-50 -50 100 100">
    <rect id="background" x="-50" y="-50" width="100" height="100" rx="4"
    fill="#f90"/>
    <rect id="top-left" x="-50" y="-50" width="50" height="50" rx="4"
    fill="#ffb13b"/>
    <rect id="bottom-right" width="50" height="50" rx="4" fill="#de8500"/>
    <use stroke="#f90" stroke-width="22.6" xlink:href="#a"/>
    <circle r="26"/>
    <use stroke="#000" stroke-width="12" xlink:href="#a"/>
    <g id="a">
        <g id="b">
            <g id="c">
                <circle id="n" cy="-31.6" r="7.1" fill="#fff"/>
                <path d="m0 31.6v-63.2" stroke="#fff" stroke-width="10"/>
                <use y="63.2" xlink:href="#n"/>
            </g>
            <use transform="rotate(90)" xlink:href="#c"/>
        </g>
        <use transform="rotate(45)" xlink:href="#b"/>
    </g>
    <path id="text-backdrop" d="m44.68 0v40c0 3.333-1.667 5-5 5h-79.38c-3.333
    0-5-1.667-5-5v-40"/>
    <path id="shine" d="m36 4.21c2.9 0 5.3 2.4 5.3
    5.3v18c-27.6-3.4-54.9-8-82-7.7v-10.2c0-2.93 2.4-5.3 5.3-5.3z"
    fill="#3f3f3f"/>
    <use stroke="#000" stroke-width="7.4" xlink:href="#s"/>
    <g id="svg-text" stroke="#fff" stroke-width="6.4">
        <g id="s">
            <path fill="none" d="m-31.74 31.17a8.26 8.26 0 1 0 8.26 -8.26 8.26
            8.26 0 1 1 8.26 -8.26M23.23 23h8.288v 8.26a8.26 8.26 0 0 1 -16.52
            0v-16.52a8.26 8.26 0 0 1 16.52 0"/>
            <g stroke-width=".5" stroke="#000">
                <path
                d="m4.76 3h6.83l-8.24 39.8h-6.85l-8.26-39.8h6.85l4.84 23.3z"
                fill="#fff"/>
                <path d="m23.23 19.55v6.9m4.838-11.71h6.9m-70.16
                16.43h6.9m9.62-16.52h6.9" stroke-linecap="square"/>
            </g>
        </g>
    </g>
    </svg>'''

    urlsvg = 'https://upload.wikimedia.org/wikipedia/commons/0/02/SVG_logo.svg'
    aioclient_mock.get(urlsvg, text=svg_image)

    cam_config_svg = {
        'name': 'config_test_svg',
        'platform': 'generic',
        'still_image_url': urlsvg,
        'content_type': 'image/svg+xml',
    }
    cam_config_normal = cam_config_svg.copy()
    cam_config_normal.pop('content_type')
    cam_config_normal['name'] = 'config_test_jpg'

    def setup_platform():
        """Setup the platform."""
        assert setup_component(hass, 'camera', {
            'camera': [cam_config_svg, cam_config_normal]})

    yield from hass.loop.run_in_executor(None, setup_platform)

    client = yield from test_client(hass.http.app)

    resp_1 = yield from client.get('/api/camera_proxy/camera.config_test_svg')
    assert aioclient_mock.call_count == 1
    assert resp_1.status == 200
    assert resp_1.content_type == 'image/svg+xml'
    body = yield from resp_1.text()
    assert body == svg_image

    resp_2 = yield from client.get('/api/camera_proxy/camera.config_test_jpg')
    assert aioclient_mock.call_count == 2
    assert resp_2.status == 200
    assert resp_2.content_type == 'image/jpeg'
    body = yield from resp_2.text()
    assert body == svg_image
