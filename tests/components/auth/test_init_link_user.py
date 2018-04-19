"""Tests for the link user flow."""

from . import async_setup_auth


async def test_link_user(hass, aiohttp_client):
    """Test linking a user to new credentials."""
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

    info = await hass.components.auth.async_resolve_token(
        hass, tokens['access_token'])
    print('info', info)
    assert info is not None
    assert len(info['user'].credentials) == 1

    # Now authenticate with the 2nd flow
    resp = await client.post('/api/auth/login_flow', json={
        'handler': ['insecure_example', '2nd auth']
    })
    assert resp.status == 200
    step = await resp.json()

    resp = await client.post(
        '/api/auth/login_flow/{}'.format(step['flow_id']), json={
            'username': '2nd-user',
            'password': '2nd-pass',
        })

    assert resp.status == 200
    step = await resp.json()
    code = step['result']

    # Link user
    resp = await client.post('/api/auth/link_user', json={
            'client_id': 'fake-client-id',
            'code': code
        }, headers={
            'authorization': 'Bearer {}'.format(tokens['access_token'])
        })

    assert resp.status == 200

    assert len(info['user'].credentials) == 2



async def test_link_user_invalid_client_id(hass):
    """Test linking a user to new credentials."""
    assert False


async def test_link_user_invalid_code(hass):
    """Test linking a user to new credentials."""
    assert False


async def test_link_user_invalid_auth(hass):
    """Test linking a user to new credentials."""
    assert False
