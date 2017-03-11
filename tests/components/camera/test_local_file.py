"""The tests for local file camera component."""
import asyncio
from unittest import mock

# Using third party package because of a bug reading binary data in Python 3.4
# https://bugs.python.org/issue23004
from mock_open import MockOpen

from homeassistant.setup import setup_component

from tests.common import mock_http_component
import logging


@asyncio.coroutine
def test_loading_file(hass, test_client):
    """Test that it loads image from disk."""
    @mock.patch('os.path.isfile', mock.Mock(return_value=True))
    @mock.patch('os.access', mock.Mock(return_value=True))
    def setup_platform():
        """Setup platform inside callback."""
        assert setup_component(hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'local_file',
                'file_path': 'mock.file',
            }})

    yield from hass.loop.run_in_executor(None, setup_platform)

    client = yield from test_client(hass.http.app)

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
    mock_http_component(hass)

    @mock.patch('os.path.isfile', mock.Mock(return_value=True))
    @mock.patch('os.access', mock.Mock(return_value=False))
    def run_test():

        caplog.set_level(
            logging.WARNING, logger='requests.packages.urllib3.connectionpool')

        assert setup_component(hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'local_file',
                'file_path': 'mock.file',
            }})
        assert 'Could not read' in caplog.text
        assert 'config_test' in caplog.text
        assert 'mock.file' in caplog.text

    yield from hass.loop.run_in_executor(None, run_test)
