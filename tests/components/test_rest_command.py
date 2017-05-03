"""The tests for the rest command platform."""
import asyncio

import aiohttp

import homeassistant.components.rest_command as rc
from homeassistant.setup import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)


class TestRestCommandSetup(object):
    """Test the rest command component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            rc.DOMAIN: {'test_get': {
                'url': 'http://example.com/'
            }}
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        with assert_setup_component(1):
            setup_component(self.hass, rc.DOMAIN, self.config)

    def test_setup_component_timeout(self):
        """Test setup component timeout."""
        self.config[rc.DOMAIN]['test_get']['timeout'] = 10

        with assert_setup_component(1):
            setup_component(self.hass, rc.DOMAIN, self.config)

    def test_setup_component_test_service(self):
        """Test setup component and check if service exits."""
        with assert_setup_component(1):
            setup_component(self.hass, rc.DOMAIN, self.config)

        assert self.hass.services.has_service(rc.DOMAIN, 'test_get')


class TestRestCommandComponent(object):
    """Test the rest command component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.url = "https://example.com/"
        self.config = {
            rc.DOMAIN: {
                'get_test': {
                    'url': self.url,
                    'method': 'get',
                },
                'post_test': {
                    'url': self.url,
                    'method': 'post',
                },
                'put_test': {
                    'url': self.url,
                    'method': 'put',
                },
                'delete_test': {
                    'url': self.url,
                    'method': 'delete',
                },
            }
        }

        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_tests(self):
        """Setup test config and test it."""
        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        assert self.hass.services.has_service(rc.DOMAIN, 'get_test')
        assert self.hass.services.has_service(rc.DOMAIN, 'post_test')
        assert self.hass.services.has_service(rc.DOMAIN, 'put_test')
        assert self.hass.services.has_service(rc.DOMAIN, 'delete_test')

    def test_rest_command_timeout(self, aioclient_mock):
        """Call a rest command with timeout."""
        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.get(self.url, exc=asyncio.TimeoutError())

        self.hass.services.call(rc.DOMAIN, 'get_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_aiohttp_error(self, aioclient_mock):
        """Call a rest command with aiohttp exception."""
        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.get(self.url, exc=aiohttp.ClientError())

        self.hass.services.call(rc.DOMAIN, 'get_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_error(self, aioclient_mock):
        """Call a rest command with status code 400."""
        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.get(self.url, status=400)

        self.hass.services.call(rc.DOMAIN, 'get_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_auth(self, aioclient_mock):
        """Call a rest command with auth credential."""
        data = {
            'username': 'test',
            'password': '123456',
        }
        self.config[rc.DOMAIN]['get_test'].update(data)

        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.get(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'get_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_form_data(self, aioclient_mock):
        """Call a rest command with post form data."""
        data = {
            'payload': 'test'
        }
        self.config[rc.DOMAIN]['post_test'].update(data)

        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.post(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'post_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == b'test'

    def test_rest_command_get(self, aioclient_mock):
        """Call a rest command with get."""
        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.get(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'get_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_delete(self, aioclient_mock):
        """Call a rest command with delete."""
        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.delete(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'delete_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_post(self, aioclient_mock):
        """Call a rest command with post."""
        data = {
            'payload': 'data',
        }
        self.config[rc.DOMAIN]['post_test'].update(data)

        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.post(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'post_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == b'data'

    def test_rest_command_put(self, aioclient_mock):
        """Call a rest command with put."""
        data = {
            'payload': 'data',
        }
        self.config[rc.DOMAIN]['put_test'].update(data)

        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.put(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'put_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == b'data'

    def test_rest_command_content_type(self, aioclient_mock):
        """Call a rest command with a content type."""
        data = {
            'payload': 'item',
            'content_type': 'text/plain'
        }
        self.config[rc.DOMAIN]['post_test'].update(data)

        with assert_setup_component(4):
            setup_component(self.hass, rc.DOMAIN, self.config)

        aioclient_mock.post(self.url, content=b'success')

        self.hass.services.call(rc.DOMAIN, 'post_test', {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == b'item'
