"""Test the Home Assistant local auth provider."""
from unittest.mock import Mock

import base64
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config, auth_store
from homeassistant.auth.providers import (
    auth_provider_from_config, homeassistant as hass_auth)


@pytest.fixture
def data(hass):
    """Create a loaded data class."""
    data = hass_auth.Data(hass)
    hass.loop.run_until_complete(data.async_load())
    return data


async def test_adding_user(data, hass):
    """Test adding a user."""
    data.add_auth('test-user', 'test-pass')
    data.validate_login('test-user', 'test-pass')


async def test_adding_user_duplicate_username(data, hass):
    """Test adding a user with duplicate username."""
    data.add_auth('test-user', 'test-pass')
    with pytest.raises(hass_auth.InvalidUser):
        data.add_auth('test-user', 'other-pass')


async def test_validating_password_invalid_user(data, hass):
    """Test validating an invalid user."""
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('non-existing', 'pw')


async def test_validating_password_invalid_password(data, hass):
    """Test validating an invalid password."""
    data.add_auth('test-user', 'test-pass')

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('test-user', 'invalid-pass')


async def test_changing_password(data, hass):
    """Test adding a user."""
    user = 'test-user'
    data.add_auth(user, 'test-pass')
    data.change_password(user, 'new-pass')

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login(user, 'test-pass')

    data.validate_login(user, 'new-pass')


async def test_changing_password_raises_invalid_user(data, hass):
    """Test that we initialize an empty config."""
    with pytest.raises(hass_auth.InvalidUser):
        data.change_password('non-existing', 'pw')


async def test_login_flow_validates(data, hass):
    """Test login flow."""
    data.add_auth('test-user', 'test-pass')
    await data.async_save()

    provider = hass_auth.HassAuthProvider(hass, auth_store.AuthStore(hass),
                                          {'type': 'homeassistant'})
    flow = await provider.async_login_flow({})
    result = await flow.async_step_init()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    result = await flow.async_step_init({
        'username': 'incorrect-user',
        'password': 'test-pass',
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors']['base'] == 'invalid_auth'

    result = await flow.async_step_init({
        'username': 'test-user',
        'password': 'incorrect-pass',
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors']['base'] == 'invalid_auth'

    result = await flow.async_step_init({
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data']['username'] == 'test-user'


async def test_saving_loading(data, hass):
    """Test saving and loading JSON."""
    data.add_auth('test-user', 'test-pass')
    data.add_auth('second-user', 'second-pass')
    await data.async_save()

    data = hass_auth.Data(hass)
    await data.async_load()
    data.validate_login('test-user', 'test-pass')
    data.validate_login('second-user', 'second-pass')


async def test_not_allow_set_id():
    """Test we are not allowed to set an ID in config."""
    hass = Mock()
    with pytest.raises(vol.Invalid):
        await auth_provider_from_config(hass, None, {
            'type': 'homeassistant',
            'id': 'invalid',
        })


async def test_new_users_populate_values(hass, data):
    """Test that we populate data for new users."""
    data.add_auth('hello', 'test-pass')
    await data.async_save()

    manager = await auth_manager_from_config(hass, [{
        'type': 'homeassistant'
    }], [])
    provider = manager.auth_providers[0]
    credentials = await provider.async_get_or_create_credentials({
        'username': 'hello'
    })
    user = await manager.async_get_or_create_user(credentials)
    assert user.name == 'hello'
    assert user.is_active


async def test_new_hashes_are_bcrypt(data, hass):
    """Test that newly created hashes are using bcrypt."""
    data.add_auth('newuser', 'newpass')
    found = None
    for user in data.users:
        if user['username'] == 'newuser':
            found = user
    assert found is not None
    user_hash = base64.b64decode(found['password'])
    assert (user_hash.startswith(b'$2a$')
            or user_hash.startswith(b'$2b$')
            or user_hash.startswith(b'$2x$')
            or user_hash.startswith(b'$2y$'))


async def test_pbkdf2_to_bcrypt_hash_upgrade(hass_storage, hass):
    """Test migrating user from pbkdf2 hash to bcrypt hash."""
    hass_storage[hass_auth.STORAGE_KEY] = {
        'version': hass_auth.STORAGE_VERSION,
        'key': hass_auth.STORAGE_KEY,
        'data': {
            'salt': '09c52f0b120eaa7dea5f73f9a9b985f3d493b30a08f3f2945ef613'
                    '0b08e6a3ea',
            'users': [
                {
                    'password': 'L5PAbehB8LAQI2Ixu+d+PDNJKmljqLnBcYWYw35onC/8D'
                                'BM1SpvT6A8ZFael5+deCt+s+43J08IcztnguouHSw==',
                    'username': 'legacyuser'
                }
            ]
        },
    }
    data = hass_auth.Data(hass)
    await data.async_load()

    # verify the correct (pbkdf2) password successfuly authenticates the user
    await hass.async_add_executor_job(
        data.validate_login, 'legacyuser', 'beer')

    # ...and that the hashes are now bcrypt hashes
    user_hash = base64.b64decode(
        hass_storage[hass_auth.STORAGE_KEY]['data']['users'][0]['password'])
    assert (user_hash.startswith(b'$2a$')
            or user_hash.startswith(b'$2b$')
            or user_hash.startswith(b'$2x$')
            or user_hash.startswith(b'$2y$'))


async def test_pbkdf2_to_bcrypt_hash_upgrade_with_incorrect_pass(hass_storage,
                                                                 hass):
    """Test migrating user from pbkdf2 hash to bcrypt hash."""
    hass_storage[hass_auth.STORAGE_KEY] = {
        'version': hass_auth.STORAGE_VERSION,
        'key': hass_auth.STORAGE_KEY,
        'data': {
            'salt': '09c52f0b120eaa7dea5f73f9a9b985f3d493b30a08f3f2945ef613'
                    '0b08e6a3ea',
            'users': [
                {
                    'password': 'L5PAbehB8LAQI2Ixu+d+PDNJKmljqLnBcYWYw35onC/8D'
                                'BM1SpvT6A8ZFael5+deCt+s+43J08IcztnguouHSw==',
                    'username': 'legacyuser'
                }
            ]
        },
    }
    data = hass_auth.Data(hass)
    await data.async_load()

    orig_user_hash = base64.b64decode(
        hass_storage[hass_auth.STORAGE_KEY]['data']['users'][0]['password'])

    # Make sure invalid legacy passwords fail
    with pytest.raises(hass_auth.InvalidAuth):
        await hass.async_add_executor_job(
            data.validate_login, 'legacyuser', 'wine')

    # Make sure we don't change the password/hash when password is incorrect
    with pytest.raises(hass_auth.InvalidAuth):
        await hass.async_add_executor_job(
            data.validate_login, 'legacyuser', 'wine')

    same_user_hash = base64.b64decode(
        hass_storage[hass_auth.STORAGE_KEY]['data']['users'][0]['password'])

    assert orig_user_hash == same_user_hash
