"""Integration tests for the auth component."""
from . import async_setup_auth, CLIENT_AUTH, CLIENT_REDIRECT_URI


async def test_login_new_user_and_refresh_token(hass, aiohttp_client):
    """Test logging in with new user and refreshing tokens."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.post('/auth/login_flow', json={
        'handler': ['insecure_example', None],
        'redirect_uri': CLIENT_REDIRECT_URI,
    }, auth=CLIENT_AUTH)
    assert resp.status == 200
    step = await resp.json()

    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': 'test-user',
            'password': 'test-pass',
        }, auth=CLIENT_AUTH)

    assert resp.status == 200
    step = await resp.json()
    code = step['result']

    # Exchange code for tokens
    resp = await client.post('/auth/token', data={
            'grant_type': 'authorization_code',
            'code': code
        }, auth=CLIENT_AUTH)

    assert resp.status == 200
    tokens = await resp.json()

    assert hass.auth.async_get_access_token(tokens['access_token']) is not None

    # Use refresh token to get more tokens.
    resp = await client.post('/auth/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token']
        }, auth=CLIENT_AUTH)

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
