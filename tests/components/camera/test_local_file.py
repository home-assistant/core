"""The tests for local file camera component."""
import asyncio
from unittest import mock

# Using third party package because of a bug reading binary data in Python 3.4
# https://bugs.python.org/issue23004
from mock_open import MockOpen

from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera.local_file import (
    SERVICE_UPDATE_FILE_PATH)
from homeassistant.setup import async_setup_component

from tests.common import mock_registry


@asyncio.coroutine
def test_loading_file(hass, aiohttp_client):
    """Test that it loads image from disk."""
    mock_registry(hass)

    with mock.patch('os.path.isfile', mock.Mock(return_value=True)), \
            mock.patch('os.access', mock.Mock(return_value=True)):
        yield from async_setup_component(hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'local_file',
                'file_path': 'mock.file',
            }})

    client = yield from aiohttp_client(hass.http.app)

    m_open = MockOpen(read_data=b'hello')
    with mock.patch(
            'homeassistant.components.camera.local_file.open',
            m_open, create=True
    ):
        resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    body = yield from resp.text()
    assert body == 'hello'


@asyncio.coroutine
def test_file_not_readable(hass, caplog):
    """Test a warning is shown setup when file is not readable."""
    with mock.patch('os.path.isfile', mock.Mock(return_value=True)), \
            mock.patch('os.access', mock.Mock(return_value=False)):
        yield from async_setup_component(hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'local_file',
                'file_path': 'mock.file',
            }})

    assert 'Could not read' in caplog.text
    assert 'config_test' in caplog.text
    assert 'mock.file' in caplog.text


@asyncio.coroutine
def test_camera_content_type(hass, aiohttp_client):
    """Test local_file camera content_type."""
    cam_config_jpg = {
        'name': 'test_jpg',
        'platform': 'local_file',
        'file_path': '/path/to/image.jpg',
    }
    cam_config_png = {
        'name': 'test_png',
        'platform': 'local_file',
        'file_path': '/path/to/image.png',
    }
    cam_config_svg = {
        'name': 'test_svg',
        'platform': 'local_file',
        'file_path': '/path/to/image.svg',
    }
    cam_config_noext = {
        'name': 'test_no_ext',
        'platform': 'local_file',
        'file_path': '/path/to/image',
    }

    yield from async_setup_component(hass, 'camera', {
        'camera': [cam_config_jpg, cam_config_png,
                   cam_config_svg, cam_config_noext]})

    client = yield from aiohttp_client(hass.http.app)

    image = 'hello'
    m_open = MockOpen(read_data=image.encode())
    with mock.patch('homeassistant.components.camera.local_file.open',
                    m_open, create=True):
        resp_1 = yield from client.get('/api/camera_proxy/camera.test_jpg')
        resp_2 = yield from client.get('/api/camera_proxy/camera.test_png')
        resp_3 = yield from client.get('/api/camera_proxy/camera.test_svg')
        resp_4 = yield from client.get('/api/camera_proxy/camera.test_no_ext')

    assert resp_1.status == 200
    assert resp_1.content_type == 'image/jpeg'
    body = yield from resp_1.text()
    assert body == image

    assert resp_2.status == 200
    assert resp_2.content_type == 'image/png'
    body = yield from resp_2.text()
    assert body == image

    assert resp_3.status == 200
    assert resp_3.content_type == 'image/svg+xml'
    body = yield from resp_3.text()
    assert body == image

    # default mime type
    assert resp_4.status == 200
    assert resp_4.content_type == 'image/jpeg'
    body = yield from resp_4.text()
    assert body == image


async def test_update_file_path(hass):
    """Test update_file_path service."""
    # Setup platform

    mock_registry(hass)

    with mock.patch('os.path.isfile', mock.Mock(return_value=True)), \
            mock.patch('os.access', mock.Mock(return_value=True)):
        await async_setup_component(hass, 'camera', {
            'camera': {
                'platform': 'local_file',
                'file_path': 'mock/path.jpg'
            }
        })

        # Fetch state and check motion detection attribute
        state = hass.states.get('camera.local_file')
        assert state.attributes.get('friendly_name') == 'Local File'
        assert state.attributes.get('file_path') == 'mock/path.jpg'

        service_data = {
            "entity_id": 'camera.local_file',
            "file_path": 'new/path.jpg'
        }

        await hass.services.async_call(DOMAIN,
                                       SERVICE_UPDATE_FILE_PATH,
                                       service_data)
        await hass.async_block_till_done()

        state = hass.states.get('camera.local_file')
        assert state.attributes.get('file_path') == 'new/path.jpg'
