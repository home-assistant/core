"""The tests for the Home Assistant HTTP component."""
import asyncio

from homeassistant.setup import async_setup_component

import homeassistant.components.http as http


class TestView(http.HomeAssistantView):
    """Test the HTTP views."""

    name = 'test'
    url = '/hello'

    @asyncio.coroutine
    def get(self, request):
        """Return a get request."""
        return 'hello'


@asyncio.coroutine
def test_registering_view_while_running(hass, test_client, unused_port):
    """Test that we can register a view while the server is running."""
    yield from async_setup_component(
        hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_SERVER_PORT: unused_port(),
            }
        }
    )

    yield from hass.async_start()
    # This raises a RuntimeError if app is frozen
    hass.http.register_view(TestView)


@asyncio.coroutine
def test_api_base_url_with_domain(hass):
    """Test setting API URL."""
    result = yield from async_setup_component(hass, 'http', {
        'http': {
            'base_url': 'example.com'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://example.com'


@asyncio.coroutine
def test_api_base_url_with_ip(hass):
    """Test setting api url."""
    result = yield from async_setup_component(hass, 'http', {
        'http': {
            'server_host': '1.1.1.1'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://1.1.1.1:8123'


@asyncio.coroutine
def test_api_base_url_with_ip_port(hass):
    """Test setting api url."""
    result = yield from async_setup_component(hass, 'http', {
        'http': {
            'base_url': '1.1.1.1:8124'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://1.1.1.1:8124'


@asyncio.coroutine
def test_api_no_base_url(hass):
    """Test setting api url."""
    result = yield from async_setup_component(hass, 'http', {
        'http': {
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://127.0.0.1:8123'


@asyncio.coroutine
def test_not_log_password(hass, unused_port, test_client, caplog):
    """Test access with password doesn't get logged."""
    result = yield from async_setup_component(hass, 'api', {
        'http': {
            http.CONF_SERVER_PORT: unused_port(),
            http.CONF_API_PASSWORD: 'some-pass'
        }
    })
    assert result

    client = yield from test_client(hass.http.app)

    resp = yield from client.get('/api/', params={
        'api_password': 'some-pass'
    })

    assert resp.status == 200
    logs = caplog.text

    # Ensure we don't log API passwords
    assert '/api/' in logs
    assert 'some-pass' not in logs
