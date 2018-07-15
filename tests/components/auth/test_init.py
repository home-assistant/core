"""Integration tests for the auth component."""
from datetime import timedelta
from unittest.mock import patch

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

    # User is not active
    assert resp.status == 400


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
