"""The tests for the Home Assistant HTTP component."""
import asyncio

from aiohttp.hdrs import (
    ORIGIN, ACCESS_CONTROL_ALLOW_ORIGIN, ACCESS_CONTROL_ALLOW_HEADERS,
    ACCESS_CONTROL_REQUEST_METHOD, ACCESS_CONTROL_REQUEST_HEADERS,
    CONTENT_TYPE)
import requests
from tests.common import get_test_instance_port, get_test_home_assistant

from homeassistant import const, setup
import homeassistant.components.http as http

API_PASSWORD = 'test1234'
SERVER_PORT = get_test_instance_port()
HTTP_BASE = '127.0.0.1:{}'.format(SERVER_PORT)
HTTP_BASE_URL = 'http://{}'.format(HTTP_BASE)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}
CORS_ORIGINS = [HTTP_BASE_URL, HTTP_BASE]

hass = None


def _url(path=''):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


# pylint: disable=invalid-name
def setUpModule():
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    setup.setup_component(
        hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_API_PASSWORD: API_PASSWORD,
                http.CONF_SERVER_PORT: SERVER_PORT,
                http.CONF_CORS_ORIGINS: CORS_ORIGINS,
            }
        }
    )

    setup.setup_component(hass, 'api')

    # Registering static path as it caused CORS to blow up
    hass.http.register_static_path(
        '/custom_components', hass.config.path('custom_components'))

    hass.start()


# pylint: disable=invalid-name
def tearDownModule():
    """Stop the Home Assistant server."""
    hass.stop()


class TestCors:
    """Test HTTP component."""

    def test_cors_allowed_with_password_in_url(self):
        """Test cross origin resource sharing with password in url."""
        req = requests.get(_url(const.URL_API),
                           params={'api_password': API_PASSWORD},
                           headers={ORIGIN: HTTP_BASE_URL})

        allow_origin = ACCESS_CONTROL_ALLOW_ORIGIN

        assert req.status_code == 200
        assert req.headers.get(allow_origin) == HTTP_BASE_URL

    def test_cors_allowed_with_password_in_header(self):
        """Test cross origin resource sharing with password in header."""
        headers = {
            const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
            ORIGIN: HTTP_BASE_URL
        }
        req = requests.get(_url(const.URL_API), headers=headers)

        allow_origin = ACCESS_CONTROL_ALLOW_ORIGIN

        assert req.status_code == 200
        assert req.headers.get(allow_origin) == HTTP_BASE_URL

    def test_cors_denied_without_origin_header(self):
        """Test cross origin resource sharing with password in header."""
        headers = {
            const.HTTP_HEADER_HA_AUTH: API_PASSWORD
        }
        req = requests.get(_url(const.URL_API), headers=headers)

        allow_origin = ACCESS_CONTROL_ALLOW_ORIGIN
        allow_headers = ACCESS_CONTROL_ALLOW_HEADERS

        assert req.status_code == 200
        assert allow_origin not in req.headers
        assert allow_headers not in req.headers

    def test_cors_preflight_allowed(self):
        """Test cross origin resource sharing preflight (OPTIONS) request."""
        headers = {
            ORIGIN: HTTP_BASE_URL,
            ACCESS_CONTROL_REQUEST_METHOD: 'GET',
            ACCESS_CONTROL_REQUEST_HEADERS: 'x-ha-access'
        }
        req = requests.options(_url(const.URL_API), headers=headers)

        allow_origin = ACCESS_CONTROL_ALLOW_ORIGIN
        allow_headers = ACCESS_CONTROL_ALLOW_HEADERS

        assert req.status_code == 200
        assert req.headers.get(allow_origin) == HTTP_BASE_URL
        assert req.headers.get(allow_headers) == \
            const.HTTP_HEADER_HA_AUTH.upper()


class TestView(http.HomeAssistantView):
    """Test the HTTP views."""

    name = 'test'
    url = '/hello'

    @asyncio.coroutine
    def get(self, request):
        """Return a get request."""
        return 'hello'


@asyncio.coroutine
def test_registering_view_while_running(hass, test_client):
    """Test that we can register a view while the server is running."""
    yield from setup.async_setup_component(
        hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_SERVER_PORT: get_test_instance_port(),
            }
        }
    )

    yield from hass.async_start()
    # This raises a RuntimeError if app is frozen
    hass.http.register_view(TestView)


@asyncio.coroutine
def test_api_base_url_with_domain(hass):
    """Test setting API URL."""
    result = yield from setup.async_setup_component(hass, 'http', {
        'http': {
            'base_url': 'example.com'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://example.com'


@asyncio.coroutine
def test_api_base_url_with_ip(hass):
    """Test setting api url."""
    result = yield from setup.async_setup_component(hass, 'http', {
        'http': {
            'server_host': '1.1.1.1'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://1.1.1.1:8123'


@asyncio.coroutine
def test_api_base_url_with_ip_port(hass):
    """Test setting api url."""
    result = yield from setup.async_setup_component(hass, 'http', {
        'http': {
            'base_url': '1.1.1.1:8124'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://1.1.1.1:8124'


@asyncio.coroutine
def test_api_no_base_url(hass):
    """Test setting api url."""
    result = yield from setup.async_setup_component(hass, 'http', {
        'http': {
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://127.0.0.1:8123'
