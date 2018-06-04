"""Tests for the login flow."""
from aiohttp.helpers import BasicAuth

from . import async_setup_auth, CLIENT_AUTH, CLIENT_REDIRECT_URI


async def test_fetch_auth_providers(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.get('/auth/providers', auth=CLIENT_AUTH)
    assert await resp.json() == [{
        'name': 'Example',
        'type': 'insecure_example',
        'id': None
    }]


async def test_fetch_auth_providers_require_valid_client(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.get('/auth/providers',
                            auth=BasicAuth('invalid', 'bla'))
    assert resp.status == 401


async def test_cannot_get_flows_in_progress(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, [])
    resp = await client.get('/auth/login_flow')
    assert resp.status == 405


async def test_invalid_username_password(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post('/auth/login_flow', json={
        'handler': ['insecure_example', None],
        'redirect_uri': CLIENT_REDIRECT_URI
    }, auth=CLIENT_AUTH)
    assert resp.status == 200
    step = await resp.json()

    # Incorrect username
    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': 'wrong-user',
            'password': 'test-pass',
        }, auth=CLIENT_AUTH)

    assert resp.status == 200
    step = await resp.json()

    assert step['step_id'] == 'init'
    assert step['errors']['base'] == 'invalid_auth'

    # Incorrect password
    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': 'test-user',
            'password': 'wrong-pass',
        }, auth=CLIENT_AUTH)

    assert resp.status == 200
    step = await resp.json()

    assert step['step_id'] == 'init'
    assert step['errors']['base'] == 'invalid_auth'
