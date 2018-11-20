"""Tests for the login flow."""
from unittest.mock import patch

from . import async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI


async def test_fetch_auth_providers(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.get('/auth/providers')
    assert resp.status == 200
    assert await resp.json() == [{
        'name': 'Example',
        'type': 'insecure_example',
        'id': None
    }]


async def test_fetch_auth_providers_onboarding(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    with patch('homeassistant.components.onboarding.async_is_onboarded',
               return_value=False):
        resp = await client.get('/auth/providers')
    assert resp.status == 400
    assert await resp.json() == {
        'message': 'Onboarding not finished',
        'code': 'onboarding_required',
    }


async def test_cannot_get_flows_in_progress(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, [])
    resp = await client.get('/auth/login_flow')
    assert resp.status == 405


async def test_invalid_username_password(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post('/auth/login_flow', json={
        'client_id': CLIENT_ID,
        'handler': ['insecure_example', None],
        'redirect_uri': CLIENT_REDIRECT_URI
    })
    assert resp.status == 200
    step = await resp.json()

    # Incorrect username
    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'client_id': CLIENT_ID,
            'username': 'wrong-user',
            'password': 'test-pass',
        })

    assert resp.status == 200
    step = await resp.json()

    assert step['step_id'] == 'init'
    assert step['errors']['base'] == 'invalid_auth'

    # Incorrect password
    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'client_id': CLIENT_ID,
            'username': 'test-user',
            'password': 'wrong-pass',
        })

    assert resp.status == 200
    step = await resp.json()

    assert step['step_id'] == 'init'
    assert step['errors']['base'] == 'invalid_auth'


async def test_login_exist_user(hass, aiohttp_client):
    """Test logging in with exist user."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {'username': 'test-user'})
    await hass.auth.async_get_or_create_user(cred)

    resp = await client.post('/auth/login_flow', json={
        'client_id': CLIENT_ID,
        'handler': ['insecure_example', None],
        'redirect_uri': CLIENT_REDIRECT_URI,
    })
    assert resp.status == 200
    step = await resp.json()

    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'client_id': CLIENT_ID,
            'username': 'test-user',
            'password': 'test-pass',
        })

    assert resp.status == 200
    step = await resp.json()
    assert step['type'] == 'create_entry'
    assert len(step['result']) > 1
