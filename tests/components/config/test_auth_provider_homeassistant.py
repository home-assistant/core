"""Test config entries API."""
import pytest

from homeassistant.auth.providers import homeassistant as prov_ha
from homeassistant.components.config import (
    auth_provider_homeassistant as auth_ha)

from tests.common import MockUser, register_auth_provider


@pytest.fixture(autouse=True)
def setup_config(hass):
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


async def test_create_auth_requires_admin(hass, hass_ws_client,
                                          hass_read_only_access_token):
    """Test create requires admin to call API."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

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


async def test_delete_requires_admin(hass, hass_ws_client,
                                     hass_read_only_access_token):
    """Test delete requires admin."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

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

    await client.send_json({
        'id': 5,
        'type': auth_ha.WS_TYPE_DELETE,
        'username': 'test-user',
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'auth_not_found'


async def test_change_password(hass, hass_ws_client, hass_access_token):
    """Test that change password succeeds with valid password."""
    provider = hass.auth.auth_providers[0]
    await provider.async_initialize()
    await hass.async_add_executor_job(
        provider.data.add_auth, 'test-user', 'test-pass')

    credentials = await provider.async_get_or_create_credentials({
        'username': 'test-user'
    })

    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    user = refresh_token.user
    await hass.auth.async_link_user(user, credentials)

    client = await hass_ws_client(hass, hass_access_token)
    await client.send_json({
        'id': 6,
        'type': auth_ha.WS_TYPE_CHANGE_PASSWORD,
        'current_password': 'test-pass',
        'new_password': 'new-pass'
    })

    result = await client.receive_json()
    assert result['success'], result
    await provider.async_validate_login('test-user', 'new-pass')


async def test_change_password_wrong_pw(hass, hass_ws_client,
                                        hass_access_token):
    """Test that change password fails with invalid password."""
    provider = hass.auth.auth_providers[0]
    await provider.async_initialize()
    await hass.async_add_executor_job(
        provider.data.add_auth, 'test-user', 'test-pass')

    credentials = await provider.async_get_or_create_credentials({
        'username': 'test-user'
    })

    refresh_token = await hass.auth.async_validate_access_token(
        hass_access_token)
    user = refresh_token.user
    await hass.auth.async_link_user(user, credentials)

    client = await hass_ws_client(hass, hass_access_token)
    await client.send_json({
        'id': 6,
        'type': auth_ha.WS_TYPE_CHANGE_PASSWORD,
        'current_password': 'wrong-pass',
        'new_password': 'new-pass'
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'invalid_password'
    with pytest.raises(prov_ha.InvalidAuth):
        await provider.async_validate_login('test-user', 'new-pass')


async def test_change_password_no_creds(hass, hass_ws_client,
                                        hass_access_token):
    """Test that change password fails with no credentials."""
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({
        'id': 6,
        'type': auth_ha.WS_TYPE_CHANGE_PASSWORD,
        'current_password': 'test-pass',
        'new_password': 'new-pass'
    })

    result = await client.receive_json()
    assert not result['success'], result
    assert result['error']['code'] == 'credentials_not_found'
