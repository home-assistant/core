"""The tests for local file camera component."""
from tempfile import NamedTemporaryFile
import unittest
from unittest import mock

from werkzeug.test import EnvironBuilder

from homeassistant.bootstrap import setup_component
from homeassistant.components.http import request_class

from tests.common import get_test_home_assistant


class TestLocalCamera(unittest.TestCase):
    """Test the local file camera component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.wsgi = mock.MagicMock()
        self.hass.config.components.append('http')

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_loading_file(self):
        """Test that it loads image from disk."""
        self.hass.wsgi = mock.MagicMock()

        with NamedTemporaryFile() as fp:
            fp.write('hello'.encode('utf-8'))
            fp.flush()

            assert setup_component(self.hass, 'camera', {
                'camera': {
                    'name': 'config_test',
                    'platform': 'local_file',
                    'file_path': fp.name,
                }})

            image_view = self.hass.wsgi.mock_calls[0][1][0]

            builder = EnvironBuilder(method='GET')
            Request = request_class()
            request = Request(builder.get_environ())
            request.authenticated = True
            resp = image_view.get(request, 'camera.config_test')

            assert resp.status_code == 200, resp.response
            assert resp.response[0].decode('utf-8') == 'hello'

    def test_file_not_readable(self):
        """Test local file will not setup when file is not readable."""
        self.hass.wsgi = mock.MagicMock()

        with NamedTemporaryFile() as fp:
            fp.write('hello'.encode('utf-8'))
            fp.flush()

            with mock.patch('os.access', return_value=False):
                assert setup_component(self.hass, 'camera', {
                    'camera': {
                        'name': 'config_test',
                        'platform': 'local_file',
                        'file_path': fp.name,
                    }})

                assert [] == self.hass.states.all()
