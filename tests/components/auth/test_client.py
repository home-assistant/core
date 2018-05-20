"""Tests for the client validator."""
from aiohttp.helpers import BasicAuth
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components.auth.client import verify_client
from homeassistant.components.http.view import HomeAssistantView

from . import async_setup_auth


@pytest.fixture
def mock_view(hass):
    """Register a view that verifies client id/secret."""
    hass.loop.run_until_complete(async_setup_component(hass, 'http', {}))

    clients = []

    class ClientView(HomeAssistantView):
        url = '/'
        name = 'bla'

        @verify_client
        async def get(self, request, client_id):
            """Handle GET request."""
            clients.append(client_id)

    hass.http.register_view(ClientView)
    return clients


async def test_verify_client(hass, aiohttp_client, mock_view):
    """Test that verify client can extract client auth from a request."""
    http_client = await async_setup_auth(hass, aiohttp_client)
    client = await hass.auth.async_create_client('Hello')

    resp = await http_client.get('/', auth=BasicAuth(client.id, client.secret))
    assert resp.status == 200
    assert mock_view == [client.id]


async def test_verify_client_no_auth_header(hass, aiohttp_client, mock_view):
    """Test that verify client will decline unknown client id."""
    http_client = await async_setup_auth(hass, aiohttp_client)

    resp = await http_client.get('/')
    assert resp.status == 401
    assert mock_view == []


async def test_verify_client_invalid_client_id(hass, aiohttp_client,
                                               mock_view):
    """Test that verify client will decline unknown client id."""
    http_client = await async_setup_auth(hass, aiohttp_client)
    client = await hass.auth.async_create_client('Hello')

    resp = await http_client.get('/', auth=BasicAuth('invalid', client.secret))
    assert resp.status == 401
    assert mock_view == []


async def test_verify_client_invalid_client_secret(hass, aiohttp_client,
                                                   mock_view):
    """Test that verify client will decline incorrect client secret."""
    http_client = await async_setup_auth(hass, aiohttp_client)
    client = await hass.auth.async_create_client('Hello')

    resp = await http_client.get('/', auth=BasicAuth(client.id, 'invalid'))
    assert resp.status == 401
    assert mock_view == []
