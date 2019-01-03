"""Test the onboarding views."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import onboarding
from homeassistant.components.onboarding import views

from tests.common import register_auth_provider

from . import mock_storage


@pytest.fixture(autouse=True)
def auth_active(hass):
    """Ensure auth is always active."""
    hass.loop.run_until_complete(register_auth_provider(hass, {
        'type': 'homeassistant'
    }))


async def test_onboarding_progress(hass, hass_storage, aiohttp_client):
    """Test fetching progress."""
    mock_storage(hass_storage, {
        'done': ['hello']
    })

    assert await async_setup_component(hass, 'onboarding', {})
    client = await aiohttp_client(hass.http.app)

    with patch.object(views, 'STEPS', ['hello', 'world']):
        resp = await client.get('/api/onboarding')

    assert resp.status == 200
    data = await resp.json()
    assert len(data) == 2
    assert data[0] == {
        'step': 'hello',
        'done': True
    }
    assert data[1] == {
        'step': 'world',
        'done': False
    }


async def test_onboarding_user_already_done(hass, hass_storage,
                                            aiohttp_client):
    """Test creating a new user when user step already done."""
    mock_storage(hass_storage, {
        'done': [views.STEP_USER]
    })

    with patch.object(onboarding, 'STEPS', ['hello', 'world']):
        assert await async_setup_component(hass, 'onboarding', {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post('/api/onboarding/users', json={
        'name': 'Test Name',
        'username': 'test-user',
        'password': 'test-pass',
    })

    assert resp.status == 403


async def test_onboarding_user(hass, hass_storage, aiohttp_client):
    """Test creating a new user."""
    mock_storage(hass_storage, {
        'done': ['hello']
    })

    assert await async_setup_component(hass, 'onboarding', {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post('/api/onboarding/users', json={
        'name': 'Test Name',
        'username': 'test-user',
        'password': 'test-pass',
    })

    assert resp.status == 200
    users = await hass.auth.async_get_users()
    assert len(users) == 1
    user = users[0]
    assert user.name == 'Test Name'
    assert len(user.credentials) == 1
    assert user.credentials[0].data['username'] == 'test-user'


async def test_onboarding_user_invalid_name(hass, hass_storage,
                                            aiohttp_client):
    """Test not providing name."""
    mock_storage(hass_storage, {
        'done': ['hello']
    })

    assert await async_setup_component(hass, 'onboarding', {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post('/api/onboarding/users', json={
        'username': 'test-user',
        'password': 'test-pass',
    })

    assert resp.status == 400


async def test_onboarding_user_race(hass, hass_storage, aiohttp_client):
    """Test race condition on creating new user."""
    mock_storage(hass_storage, {
        'done': ['hello']
    })

    assert await async_setup_component(hass, 'onboarding', {})

    client = await aiohttp_client(hass.http.app)

    resp1 = client.post('/api/onboarding/users', json={
        'name': 'Test 1',
        'username': '1-user',
        'password': '1-pass',
    })
    resp2 = client.post('/api/onboarding/users', json={
        'name': 'Test 2',
        'username': '2-user',
        'password': '2-pass',
    })

    res1, res2 = await asyncio.gather(resp1, resp2)

    assert sorted([res1.status, res2.status]) == [200, 403]
