"""The tests for the Home Assistant HTTP component."""
from homeassistant.setup import async_setup_component

import homeassistant.components.http as http


class TestView(http.HomeAssistantView):
    """Test the HTTP views."""

    name = 'test'
    url = '/hello'

    async def get(self, request):
        """Return a get request."""
        return 'hello'


async def test_registering_view_while_running(hass, aiohttp_client,
                                              aiohttp_unused_port):
    """Test that we can register a view while the server is running."""
    await async_setup_component(
        hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_SERVER_PORT: aiohttp_unused_port(),
            }
        }
    )

    await hass.async_start()
    # This raises a RuntimeError if app is frozen
    hass.http.register_view(TestView)


async def test_api_base_url_with_domain(hass):
    """Test setting API URL."""
    result = await async_setup_component(hass, 'http', {
        'http': {
            'base_url': 'example.com'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://example.com'


async def test_api_base_url_with_ip(hass):
    """Test setting api url."""
    result = await async_setup_component(hass, 'http', {
        'http': {
            'server_host': '1.1.1.1'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://1.1.1.1:8123'


async def test_api_base_url_with_ip_port(hass):
    """Test setting api url."""
    result = await async_setup_component(hass, 'http', {
        'http': {
            'base_url': '1.1.1.1:8124'
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://1.1.1.1:8124'


async def test_api_no_base_url(hass):
    """Test setting api url."""
    result = await async_setup_component(hass, 'http', {
        'http': {
        }
    })
    assert result
    assert hass.config.api.base_url == 'http://127.0.0.1:8123'


async def test_not_log_password(hass, aiohttp_client, caplog):
    """Test access with password doesn't get logged."""
    result = await async_setup_component(hass, 'api', {
        'http': {
            http.CONF_API_PASSWORD: 'some-pass'
        }
    })
    assert result

    client = await aiohttp_client(hass.http.app)

    resp = await client.get('/api/', params={
        'api_password': 'some-pass'
    })

    assert resp.status == 200
    logs = caplog.text

    # Ensure we don't log API passwords
    assert '/api/' in logs
    assert 'some-pass' not in logs
