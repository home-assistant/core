"""Test config entries API."""
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.auth import models as auth_models
from homeassistant.components.config import auth as auth_config

from tests.common import MockUser, CLIENT_ID


@pytest.fixture(autouse=True)
def auth_active(hass):
    """Mock that auth is active."""
    with patch('homeassistant.auth.AuthManager.active',
               PropertyMock(return_value=True)):
        yield


@pytest.fixture(autouse=True)
def setup_config(hass, aiohttp_client):
    """Fixture that sets up the auth provider homeassistant module."""
    hass.loop.run_until_complete(auth_config.async_setup(hass))


async def test_list_requires_owner(hass, hass_ws_client, hass_access_token):
    """Test get users requires auth."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_LIST,
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'


async def test_list(hass, hass_ws_client):
    """Test get users."""
    owner = MockUser(
        id='abc',
        name='Test Owner',
        is_owner=True,
    ).add_to_hass(hass)

    owner.credentials.append(auth_models.Credentials(
        auth_provider_type='homeassistant',
        auth_provider_id=None,
        data={},
    ))

    system = MockUser(
        id='efg',
        name='Test Hass.io',
        system_generated=True
    ).add_to_hass(hass)

    inactive = MockUser(
        id='hij',
        name='Inactive User',
        is_active=False,
    ).add_to_hass(hass)

    refresh_token = await hass.auth.async_create_refresh_token(
        owner, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    client = await hass_ws_client(hass, access_token)
    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_LIST,
    })

    result = await client.receive_json()
    assert result['success'], result
    data = result['result']
    assert len(data) == 3
    assert data[0] == {
        'id': owner.id,
        'name': 'Test Owner',
        'is_owner': True,
        'is_active': True,
        'system_generated': False,
        'credentials': [{'type': 'homeassistant'}]
    }
    assert data[1] == {
        'id': system.id,
        'name': 'Test Hass.io',
        'is_owner': False,
        'is_active': True,
        'system_generated': True,
        'credentials': [],
    }
    assert data[2] == {
        'id': inactive.id,
        'name': 'Inactive User',
        'is_owner': False,
        'is_active': False,
        'system_generated': False,
        'credentials': [],
    }


async def test_delete_requires_owner(hass, hass_ws_client, hass_access_token):
    """Test delete command requires an owner."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_DELETE,
        'user_id': 'abcd',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'


async def test_delete_unable_self_account(hass, hass_ws_client,
                                          hass_access_token):
    """Test we cannot delete our own account."""
    client = await hass_ws_client(hass, hass_access_token)
    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_DELETE,
        'user_id': refresh_token.user.id,
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'


async def test_delete_unknown_user(hass, hass_ws_client, hass_access_token):
    """Test we cannot delete an unknown user."""
    client = await hass_ws_client(hass, hass_access_token)
    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    refresh_token.user.is_owner = True

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_DELETE,
        'user_id': 'abcd',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'not_found'


async def test_delete(hass, hass_ws_client, hass_access_token):
    """Test delete command works."""
    client = await hass_ws_client(hass, hass_access_token)
    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    refresh_token.user.is_owner = True
    test_user = MockUser(
        id='efg',
    ).add_to_hass(hass)

    assert len(await hass.auth.async_get_users()) == 2

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_DELETE,
        'user_id': test_user.id,
    })

    result = await client.receive_json()
    assert result['success'], result
    assert len(await hass.auth.async_get_users()) == 1


async def test_create(hass, hass_ws_client, hass_access_token):
    """Test create command works."""
    client = await hass_ws_client(hass, hass_access_token)
    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    refresh_token.user.is_owner = True

    assert len(await hass.auth.async_get_users()) == 1

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_CREATE,
        'name': 'Paulus',
    })

    result = await client.receive_json()
    assert result['success'], result
    assert len(await hass.auth.async_get_users()) == 2
    data_user = result['result']['user']
    user = await hass.auth.async_get_user(data_user['id'])
    assert user is not None
    assert user.name == data_user['name']
    assert user.is_active
    assert not user.is_owner
    assert not user.system_generated


async def test_create_requires_owner(hass, hass_ws_client, hass_access_token):
    """Test create command requires an owner."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth_config.WS_TYPE_CREATE,
        'name': 'YO',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'
