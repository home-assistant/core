"""The tests for generic camera component."""
import unittest
from unittest import mock

import requests_mock
from werkzeug.test import EnvironBuilder

from homeassistant.bootstrap import setup_component
from homeassistant.components.http import request_class

from tests.common import get_test_home_assistant


class TestGenericCamera(unittest.TestCase):
    """Test the generic camera platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.wsgi = mock.MagicMock()
        self.hass.config.components.append('http')

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_fetching_url(self, m):
        """Test that it fetches the given url."""
        self.hass.wsgi = mock.MagicMock()
        m.get('http://example.com', text='hello world')

        assert setup_component(self.hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'generic',
                'still_image_url': 'http://example.com',
                'username': 'user',
                'password': 'pass'
            }})

        image_view = self.hass.wsgi.mock_calls[0][1][0]

        builder = EnvironBuilder(method='GET')
        Request = request_class()
        request = Request(builder.get_environ())
        request.authenticated = True
        resp = image_view.get(request, 'camera.config_test')

        assert m.call_count == 1
        assert resp.status_code == 200, resp.response
        assert resp.response[0].decode('utf-8') == 'hello world'

        image_view.get(request, 'camera.config_test')
        assert m.call_count == 2

    @requests_mock.Mocker()
    def test_limit_refetch(self, m):
        """Test that it fetches the given url."""
        self.hass.wsgi = mock.MagicMock()
        from requests.exceptions import Timeout
        m.get('http://example.com/5a', text='hello world')
        m.get('http://example.com/10a', text='hello world')
        m.get('http://example.com/15a', text='hello planet')
        m.get('http://example.com/20a', status_code=404)

        assert setup_component(self.hass, 'camera', {
            'camera': {
                'name': 'config_test',
                'platform': 'generic',
                'still_image_url':
                'http://example.com/{{ states.sensor.temp.state + "a" }}',
                'limit_refetch_to_url_change': True,
            }})

        image_view = self.hass.wsgi.mock_calls[0][1][0]

        builder = EnvironBuilder(method='GET')
        Request = request_class()
        request = Request(builder.get_environ())
        request.authenticated = True

        self.hass.states.set('sensor.temp', '5')

        with mock.patch('requests.get', side_effect=Timeout()):
            resp = image_view.get(request, 'camera.config_test')
            assert m.call_count == 0
            assert resp.status_code == 500, resp.response

        self.hass.states.set('sensor.temp', '10')

        resp = image_view.get(request, 'camera.config_test')
        assert m.call_count == 1
        assert resp.status_code == 200, resp.response
        assert resp.response[0].decode('utf-8') == 'hello world'

        resp = image_view.get(request, 'camera.config_test')
        assert m.call_count == 1
        assert resp.status_code == 200, resp.response
        assert resp.response[0].decode('utf-8') == 'hello world'

        self.hass.states.set('sensor.temp', '15')

        # Url change = fetch new image
        resp = image_view.get(request, 'camera.config_test')
        assert m.call_count == 2
        assert resp.status_code == 200, resp.response
        assert resp.response[0].decode('utf-8') == 'hello planet'

        # Cause a template render error
        self.hass.states.remove('sensor.temp')
        resp = image_view.get(request, 'camera.config_test')
        assert m.call_count == 2
        assert resp.status_code == 200, resp.response
        assert resp.response[0].decode('utf-8') == 'hello planet'
