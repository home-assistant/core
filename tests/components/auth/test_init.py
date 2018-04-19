"""Tests for the auth component."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant import auth as auth_core
from homeassistant.components import auth as auth_cmp
from homeassistant.setup import async_setup_component

from tests.common import MockUser


from . import async_setup_auth


async def test_fetch_auth_providers(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
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
    client = await async_setup_auth(hass, aiohttp_client)
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


async def test_login_new_user_and_refresh_token(hass, aiohttp_client):
    """Test logging in with new user and refreshing tokens."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
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

    assert await hass.components.auth.async_resolve_token(
        hass, tokens['access_token']) is not None

    # Use refresh token to get more tokens.
    resp = await client.post('/api/auth/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token']
        })

    assert resp.status == 200
    tokens = await resp.json()
    assert 'refresh_token' not in tokens
    assert await hass.components.auth.async_resolve_token(
        hass, tokens['access_token']) is not None

    # Test using access token to hit API.
    resp = await client.get('/api/')
    assert resp.status == 401

    resp = await client.get('/api/', headers={
        'authorization': 'Bearer {}'.format(tokens['access_token'])
    })
    assert resp.status == 200
