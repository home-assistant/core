"""The tests for local file camera component."""
import asyncio
from unittest import mock

from homeassistant.bootstrap import setup_component

from tests.common import assert_setup_component, mock_http_component


@asyncio.coroutine
def test_loading_file(hass, test_client):
    """Test that it loads image from disk."""
    test_string = 'hello'

    def setup_platform():
        """Setup platform inside callback."""
        with mock.patch('os.path.isfile', mock.Mock(return_value=True)), \
                mock.patch('os.access', mock.Mock(return_value=True)):
            assert setup_component(hass, 'camera', {
                'camera': {
                    'name': 'config_test',
                    'platform': 'local_file',
                    'file_path': 'mock.file',
                }})

    yield from hass.loop.run_in_executor(None, setup_platform)

    client = yield from test_client(hass.wsgi.app)

    m_open = mock.mock_open(read_data=test_string.encode('utf-8'))
    with mock.patch(
            'homeassistant.components.camera.local_file.open',
            m_open, create=True
    ):
        resp = yield from client.get('/api/camera_proxy/camera.config_test')

    assert resp.status == 200
    body = yield from resp.text()
    assert body == test_string


@asyncio.coroutine
def test_file_not_readable(hass):
    """Test local file will not setup when file is not readable."""
    mock_http_component(hass)

    def run_test():
        with mock.patch('os.path.isfile', mock.Mock(return_value=True)), \
                mock.patch('os.access', return_value=False), \
                assert_setup_component(0, 'camera'):
            assert setup_component(hass, 'camera', {
                'camera': {
                    'name': 'config_test',
                    'platform': 'local_file',
                    'file_path': 'mock.file',
                }})

    yield from hass.loop.run_in_executor(None, run_test)
