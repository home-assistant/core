"""Tests for the auth component."""
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
    if setup_api:
        await async_setup_component(hass, 'api', {})
    return await aiohttp_client(hass.http.app)
