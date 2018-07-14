"""Test config entries API."""
import pytest

from homeassistant.auth.providers import homeassistant as prov_ha
from homeassistant.components.config import (
    auth_provider_homeassistant as auth_ha)

from tests.common import MockUser, register_auth_provider


@pytest.fixture(autouse=True)
def setup_config(hass, aiohttp_client):
    """Fixture that sets up the auth provider homeassistant module."""
    hass.loop.run_until_complete(register_auth_provider(hass, {
        'type': 'homeassistant'
    }))
    hass.loop.run_until_complete(auth_ha.async_setup(hass))


async def test_create_auth_system_generated_user(hass, hass_access_token,
                                                 hass_ws_client):
    """Test we can't add auth to system generated users."""
    system_user = MockUser(system_generated=True).add_to_hass(hass)
    client = await hass_ws_client(hass, hass_access_token)
    hass_access_token.refresh_token.user.is_owner = True

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_CREATE,
        'user_id': system_user.id,
        'username': 'test-user',
        'password': 'test-pass',
    })

    result = await client.receive_json()

    assert not result['success'], result
    assert result['error']['code'] == 'system_generated'


async def test_create_auth_user_already_credentials():
    """Test we can't create auth for user with pre-existing credentials."""
    # assert False


async def test_create_auth_unknown_user(hass_ws_client, hass,
                                        hass_access_token):
    """Test create pointing at unknown user."""
    client = await hass_ws_client(hass, hass_access_token)
    hass_access_token.refresh_token.user.is_owner = True

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_CREATE,
        'user_id': 'test-id',
        'username': 'test-user',
        'password': 'test-pass',
    })

    result = await client.receive_json()

    assert not result['success'], result
    assert result['error']['code'] == 'not_found'


async def test_create_auth_requires_owner(hass, hass_ws_client,
                                          hass_access_token):
    """Test create requires owner to call API."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_CREATE,
        'user_id': 'test-id',
        'username': 'test-user',
        'password': 'test-pass',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'


async def test_create_auth(hass, hass_ws_client, hass_access_token,
                           hass_storage):
    """Test create auth command works."""
    client = await hass_ws_client(hass, hass_access_token)
    user = MockUser().add_to_hass(hass)
    hass_access_token.refresh_token.user.is_owner = True

    assert len(user.credentials) == 0

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_CREATE,
        'user_id': user.id,
        'username': 'test-user',
        'password': 'test-pass',
    })

    result = await client.receive_json()
    assert result['success'], result
    assert len(user.credentials) == 1
    creds = user.credentials[0]
    assert creds.auth_provider_type == 'homeassistant'
    assert creds.auth_provider_id is None
    assert creds.data == {
        'username': 'test-user'
    }
    assert prov_ha.STORAGE_KEY in hass_storage
    entry = hass_storage[prov_ha.STORAGE_KEY]['data']['users'][0]
    assert entry['username'] == 'test-user'


async def test_create_auth_duplicate_username(hass, hass_ws_client,
                                              hass_access_token, hass_storage):
    """Test we can't create auth with a duplicate username."""
    client = await hass_ws_client(hass, hass_access_token)
    user = MockUser().add_to_hass(hass)
    hass_access_token.refresh_token.user.is_owner = True

    hass_storage[prov_ha.STORAGE_KEY] = {
        'version': 1,
        'data': {
            'users': [{
                'username': 'test-user'
            }]
        }
    }

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_CREATE,
        'user_id': user.id,
        'username': 'test-user',
        'password': 'test-pass',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'username_exists'


async def test_delete_removes_just_auth(hass_ws_client, hass, hass_storage,
                                        hass_access_token):
    """Test deleting an auth without being connected to a user."""
    client = await hass_ws_client(hass, hass_access_token)
    hass_access_token.refresh_token.user.is_owner = True

    hass_storage[prov_ha.STORAGE_KEY] = {
        'version': 1,
        'data': {
            'users': [{
                'username': 'test-user'
            }]
        }
    }

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_DELETE,
        'username': 'test-user',
    })

    result = await client.receive_json()
    assert result['success'], result
    assert len(hass_storage[prov_ha.STORAGE_KEY]['data']['users']) == 0


async def test_delete_removes_credential(hass, hass_ws_client,
                                         hass_access_token, hass_storage):
    """Test deleting auth that is connected to a user."""
    client = await hass_ws_client(hass, hass_access_token)
    hass_access_token.refresh_token.user.is_owner = True

    user = MockUser().add_to_hass(hass)
    user.credentials.append(
        await hass.auth.auth_providers[0].async_get_or_create_credentials({
            'username': 'test-user'}))

    hass_storage[prov_ha.STORAGE_KEY] = {
        'version': 1,
        'data': {
            'users': [{
                'username': 'test-user'
            }]
        }
    }

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_DELETE,
        'username': 'test-user',
    })

    result = await client.receive_json()
    assert result['success'], result
    assert len(hass_storage[prov_ha.STORAGE_KEY]['data']['users']) == 0


async def test_delete_requires_owner(hass, hass_ws_client, hass_access_token):
    """Test delete requires owner."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_DELETE,
        'username': 'test-user',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'unauthorized'


async def test_delete_unknown_auth(hass, hass_ws_client, hass_access_token):
    """Test trying to delete an unknown auth username."""
    client = await hass_ws_client(hass, hass_access_token)
    hass_access_token.refresh_token.user.is_owner = True

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_DELETE,
        'username': 'test-user',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'auth_not_found'
