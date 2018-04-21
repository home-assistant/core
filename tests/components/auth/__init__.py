"""Tests for the auth component."""
from aiohttp.helpers import BasicAuth

from homeassistant import auth
from homeassistant.setup import async_setup_component

from tests.common import ensure_auth_manager_loaded


BASE_CONFIG = [{
    'name': 'Example',
    'type': 'insecure_example',
    'users': [{
        'username': 'test-user',
        'password': 'test-pass',
        'name': 'Test Name'
    }]
}]
CLIENT_ID = 'test-id'
CLIENT_SECRET = 'test-secret'
CLIENT_AUTH = BasicAuth(CLIENT_ID, CLIENT_SECRET)


async def async_setup_auth(hass, aiohttp_client, provider_configs=BASE_CONFIG,
                           setup_api=False):
    """Helper to setup authentication and create a HTTP client."""
    hass.auth = await auth.auth_manager_from_config(hass, provider_configs)
    ensure_auth_manager_loaded(hass.auth)
    await async_setup_component(hass, 'auth', {
        'http': {
            'api_password': 'bla'
        }
    })
    client = auth.Client('Test Client', CLIENT_ID, CLIENT_SECRET)
    hass.auth._store.clients[client.id] = client
    if setup_api:
        await async_setup_component(hass, 'api', {})
    return await aiohttp_client(hass.http.app)
