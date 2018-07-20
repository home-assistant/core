"""Integration tests for the auth component."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow
from homeassistant.components import auth

from . import async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI


async def test_login_new_user_and_trying_refresh_token(hass, aiohttp_client):
    """Test logging in with new user and refreshing tokens."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
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
    code = step['result']

    # Exchange code for tokens
    resp = await client.post('/auth/token', data={
        'client_id': CLIENT_ID,
        'grant_type': 'authorization_code',
        'code': code
    })

    assert resp.status == 200
    tokens = await resp.json()

    assert hass.auth.async_get_access_token(tokens['access_token']) is not None

    # Use refresh token to get more tokens.
    resp = await client.post('/auth/token', data={
            'client_id': CLIENT_ID,
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token']
        })

    assert resp.status == 200
    tokens = await resp.json()
    assert 'refresh_token' not in tokens
    assert hass.auth.async_get_access_token(tokens['access_token']) is not None

    # Test using access token to hit API.
    resp = await client.get('/api/')
    assert resp.status == 401

    resp = await client.get('/api/', headers={
        'authorization': 'Bearer {}'.format(tokens['access_token'])
    })
    assert resp.status == 200


def test_credential_store_expiration():
    """Test that the credential store will not return expired tokens."""
    store, retrieve = auth._create_cred_store()
    client_id = 'bla'
    credentials = 'creds'
    now = utcnow()

    with patch('homeassistant.util.dt.utcnow', return_value=now):
        code = store(client_id, credentials)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now + timedelta(minutes=10)):
        assert retrieve(client_id, code) is None

    with patch('homeassistant.util.dt.utcnow', return_value=now):
        code = store(client_id, credentials)

    with patch('homeassistant.util.dt.utcnow',
               return_value=now + timedelta(minutes=9, seconds=59)):
        assert retrieve(client_id, code) == credentials


async def test_ws_current_user(hass, hass_ws_client, hass_access_token):
    """Test the current user command."""
    assert await async_setup_component(hass, 'auth', {
        'http': {
            'api_password': 'bla'
        }
    })
    with patch('homeassistant.auth.AuthManager.active', return_value=True):
        client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth.WS_TYPE_CURRENT_USER,
    })

    result = await client.receive_json()
    assert result['success'], result

    user = hass_access_token.refresh_token.user
    user_dict = result['result']

    assert user_dict['name'] == user.name
    assert user_dict['id'] == user.id
    assert user_dict['is_owner'] == user.is_owner


async def test_cors_on_token(hass, aiohttp_client):
    """Test logging in with new user and refreshing tokens."""
    client = await async_setup_auth(hass, aiohttp_client)

    resp = await client.options('/auth/token', headers={
        'origin': 'http://example.com',
        'Access-Control-Request-Method': 'POST',
    })
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://example.com'
    assert resp.headers['Access-Control-Allow-Methods'] == 'POST'

    resp = await client.post('/auth/token', headers={
        'origin': 'http://example.com'
    })
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://example.com'
