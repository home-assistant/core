"""The tests for the rest command platform."""
import asyncio

import aiohttp

import homeassistant.components.rest_command as rc
from homeassistant.bootstrap import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)


class TestRestCommandSetup(object):
    """Test the rest command component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {
            rc.DOMAIN: {}
        }

        with assert_setup_component(1):
            setup_component(self.hass, rc.DOMAIN, config)

    def test_setup_component_timeout(self):
        """Test setup component timeout."""
        config = {
            rc.DOMAIN: {
                'timeout': 10,
            }
        }

        with assert_setup_component(1):
            setup_component(self.hass, rc.DOMAIN, config)

    def test_setup_component_test_service(self):
        """Test setup component and check if service exits."""
        config = {
            rc.DOMAIN: {}
        }

        with assert_setup_component(1):
            setup_component(self.hass, rc.DOMAIN, config)

        assert self.hass.services.has_service(rc.DOMAIN, rc.SERVICE_GET)
        assert self.hass.services.has_service(rc.DOMAIN, rc.SERVICE_POST)
        assert self.hass.services.has_service(rc.DOMAIN, rc.SERVICE_PUT)
        assert self.hass.services.has_service(rc.DOMAIN, rc.SERVICE_DELETE)


class TestRestCommandComponent(object):
    """Test the rest command component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        config = {
            rc.DOMAIN: {}
        }

        self.hass = get_test_home_assistant()
        setup_component(self.hass, rc.DOMAIN, config)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_rest_command_timeout(self, aioclient_mock):
        """Call a rest command with timeout."""
        url = "https://example.com/"
        data = {
            'url': url,
        }

        aioclient_mock.get(url, exc=asyncio.TimeoutError())

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_GET, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_aiohttp_error(self, aioclient_mock):
        """Call a rest command with aiohttp exception."""
        url = "https://example.com/"
        data = {
            'url': url,
        }

        aioclient_mock.get(url, exc=aiohttp.errors.ClientError())

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_GET, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_error(self, aioclient_mock):
        """Call a rest command with status code 400."""
        url = "https://example.com/"
        data = {
            'url': url,
        }

        aioclient_mock.get(url, status=400)

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_GET, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_auth(self, aioclient_mock):
        """Call a rest command with auth credential."""
        url = "https://example.com/"
        data = {
            'url': url,
            'username': 'test',
            'password': '123456',
        }

        aioclient_mock.get(url, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_GET, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_params(self, aioclient_mock):
        """Call a rest command with url query params."""
        url = "https://example.com/"
        params = {
            'idx': '5',
            'token': 'xy',
        }
        data = {
            'url': url,
            'params': params,
        }

        aioclient_mock.get(url, params=params, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_GET, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_form_data(self, aioclient_mock):
        """Call a rest command with post form data."""
        url = "https://example.com/"
        payload = {
            'name': 'Maier',
            'sex': 'm',
        }
        data = {
            'url': url,
            'payload': payload,
        }

        aioclient_mock.post(url, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_POST, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == payload

    def test_rest_command_get(self, aioclient_mock):
        """Call a rest command with get."""
        url = "https://example.com/"
        data = {
            'url': url,
        }

        aioclient_mock.get(url, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_GET, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_delete(self, aioclient_mock):
        """Call a rest command with delete."""
        url = "https://example.com/"
        data = {
            'url': url,
        }

        aioclient_mock.delete(url, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_DELETE, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_post(self, aioclient_mock):
        """Call a rest command with post."""
        url = "https://example.com/"
        data = {
            'url': url,
            'payload': 'data',
        }

        aioclient_mock.post(url, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_POST, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == b'data'

    def test_rest_command_put(self, aioclient_mock):
        """Call a rest command with put."""
        url = "https://example.com/"
        data = {
            'url': url,
            'payload': 'data',
        }

        aioclient_mock.put(url, content=b'success')

        self.hass.services.call(rc.DOMAIN, rc.SERVICE_PUT, data)
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == b'data'
