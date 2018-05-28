"""Tests for the link user flow."""
from . import async_setup_auth, CLIENT_AUTH, CLIENT_ID, CLIENT_REDIRECT_URI


async def async_get_code(hass, aiohttp_client):
    """Helper for link user tests that returns authorization code."""
    config = [{
        'name': 'Example',
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }, {
        'name': 'Example',
        'id': '2nd auth',
        'type': 'insecure_example',
        'users': [{
            'username': '2nd-user',
            'password': '2nd-pass',
            'name': '2nd Name'
        }]
    }]
    client = await async_setup_auth(hass, aiohttp_client, config)

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

    access_token = hass.auth.async_get_access_token(tokens['access_token'])
    assert access_token is not None
    user = access_token.refresh_token.user
    assert len(user.credentials) == 1

    # Now authenticate with the 2nd flow
    resp = await client.post('/auth/login_flow', json={
        'handler': ['insecure_example', '2nd auth'],
        'redirect_uri': CLIENT_REDIRECT_URI,
    }, auth=CLIENT_AUTH)
    assert resp.status == 200
    step = await resp.json()

    resp = await client.post(
        '/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': '2nd-user',
            'password': '2nd-pass',
        }, auth=CLIENT_AUTH)

    assert resp.status == 200
    step = await resp.json()

    return {
        'user': user,
        'code': step['result'],
        'client': client,
        'tokens': tokens,
    }


async def test_link_user(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info['client']
    code = info['code']
    tokens = info['tokens']

    # Link user
    resp = await client.post('/auth/link_user', json={
            'client_id': CLIENT_ID,
            'code': code
        }, headers={
            'authorization': 'Bearer {}'.format(tokens['access_token'])
        })

    assert resp.status == 200
    assert len(info['user'].credentials) == 2


async def test_link_user_invalid_client_id(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info['client']
    code = info['code']
    tokens = info['tokens']

    # Link user
    resp = await client.post('/auth/link_user', json={
            'client_id': 'invalid',
            'code': code
        }, headers={
            'authorization': 'Bearer {}'.format(tokens['access_token'])
        })

    assert resp.status == 400
    assert len(info['user'].credentials) == 1


async def test_link_user_invalid_code(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info['client']
    tokens = info['tokens']

    # Link user
    resp = await client.post('/auth/link_user', json={
            'client_id': CLIENT_ID,
            'code': 'invalid'
        }, headers={
            'authorization': 'Bearer {}'.format(tokens['access_token'])
        })

    assert resp.status == 400
    assert len(info['user'].credentials) == 1


async def test_link_user_invalid_auth(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info['client']
    code = info['code']

    # Link user
    resp = await client.post('/auth/link_user', json={
            'client_id': CLIENT_ID,
            'code': code,
        }, headers={'authorization': 'Bearer invalid'})

    assert resp.status == 401
    assert len(info['user'].credentials) == 1
