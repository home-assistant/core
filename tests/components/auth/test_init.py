"""Tests for the auth component."""
import pytest

from homeassistant import auth
from homeassistant.setup import async_setup_component


BASE_CONFIG = [{
    'name': 'Example',
    'type': 'insecure_example',
    'users': [{
        'username': 'test-user',
        'password': 'test-pass',
        'name': 'Test Name'
    }]
}]


async def async_setup_auth(hass, aiohttp_client, provider_configs):
    """Helper to setup authentication and create a HTTP client."""
    hass.auth = await auth.auth_manager_from_config(hass, provider_configs)
    await async_setup_component(hass, 'auth', {
        'http': {
            'api_password': 'bla'
        }
    })
    await async_setup_component(hass, 'api', {})
    return await aiohttp_client(hass.http.app)


async def test_fetch_auth_providers(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client, BASE_CONFIG)
    resp = await client.get('/api/auth/providers')
    assert await resp.json() == [{
        'name': 'Example',
        'type': 'insecure_example',
        'id': None
    }]


async def test_cannot_get_flows_in_progress(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, [])
    resp = await client.get('/api/auth/login_flow')
    assert resp.status == 405


async def test_invalid_username_password(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, BASE_CONFIG)
    resp = await client.post('/api/auth/login_flow', json={
        'handler': ['insecure_example', None]
    })
    assert resp.status == 200
    step = await resp.json()

    # Incorrect username
    resp = await client.post(
        '/api/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': 'wrong-user',
            'password': 'test-pass',
        })

    assert resp.status == 200
    step = await resp.json()

    assert step['step_id'] == 'init'
    assert step['errors']['username'] == 'Invalid username'

    # Incorrect password
    resp = await client.post(
        '/api/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': 'test-user',
            'password': 'wrong-pass',
        })

    assert resp.status == 200
    step = await resp.json()

    assert step['step_id'] == 'init'
    assert step['errors']['password'] == 'Invalid password'


async def test_login_new_user(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, BASE_CONFIG)
    resp = await client.post('/api/auth/login_flow', json={
        'handler': ['insecure_example', None]
    })
    assert resp.status == 200
    step = await resp.json()

    resp = await client.post(
        '/api/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': 'test-user',
            'password': 'test-pass',
        })

    assert resp.status == 200
    step = await resp.json()
    code = step['result']

    # Exchange code for tokens
    resp = await client.post('/api/auth/token', data={
            'grant_type': 'authorization_code',
            'code': code
        })

    assert resp.status == 200
    tokens = await resp.json()

    assert await hass.components.auth.async_valid_access_token(
        tokens['access_token'])

    # Use refresh token to get more tokens.
    resp = await client.post('/api/auth/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token']
        })

    assert resp.status == 200
    tokens = await resp.json()
    assert 'refresh_token' not in tokens
    assert await hass.components.auth.async_valid_access_token(
        tokens['access_token'])

    resp = await client.get('/api/')
    assert resp.status == 401

    resp = await client.get('/api/', headers={
        'authorization': 'Bearer {}'.format(tokens['access_token'])
    })
    assert resp.status == 200


async def test_decline_access_token_issued_too_old(hass):
    """Decline access tokens if issued before user.token_min_issued."""
    assert False


async def test_decline_refresh_token_issued_too_old(hass):
    """Decline refresh tokens if issued before user.token_min_issued."""
    assert False


async def test_decline_access_token_user_not_active(hass):
    """Decline access tokens if user is not marked as active."""
    assert False


async def test_decline_refresh_token_user_not_active(hass):
    """Decline refresh tokens if user is not marked as active."""
    assert False


async def test_decline_access_token_user_no_longer_exists(hass):
    """Decline access tokens if user no longer exists."""
    assert False


async def test_decline_refresh_token_user_no_longer_exists(hass):
    """Decline refresh tokens if user no longer exists."""
    assert False


async def test_link_user(hass):
    """Test linking a user to new credentials."""
    assert False


async def test_link_user_invalid_client_id(hass):
    """Test linking a user to new credentials."""
    assert False


async def test_link_user_invalid_code(hass):
    """Test linking a user to new credentials."""
    assert False


async def test_link_user_invalid_auth(hass):
    """Test linking a user to new credentials."""
    assert False
