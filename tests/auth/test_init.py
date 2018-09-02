"""Tests for the Home Assistant auth module."""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

from homeassistant import auth, data_entry_flow
from homeassistant.auth import (
    models as auth_models, auth_store, const as auth_const)
from homeassistant.auth.mfa_modules import SESSION_EXPIRATION
from homeassistant.util import dt as dt_util
from tests.common import (
    MockUser, ensure_auth_manager_loaded, flush_store, CLIENT_ID)


@pytest.fixture
def mock_hass(loop):
    """Hass mock with minimum amount of data set to make it work with auth."""
    hass = Mock()
    hass.config.skip_pip = True
    return hass


async def test_auth_manager_from_config_validates_config(mock_hass):
    """Test get auth providers."""
    with pytest.raises(vol.Invalid):
        manager = await auth.auth_manager_from_config(mock_hass, [{
            'name': 'Test Name',
            'type': 'insecure_example',
            'users': [],
        }, {
            'name': 'Invalid config because no users',
            'type': 'insecure_example',
            'id': 'invalid_config',
        }], [])

    manager = await auth.auth_manager_from_config(mock_hass, [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'users': [],
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
        'users': [],
    }], [])

    providers = [{
        'name': provider.name,
        'id': provider.id,
        'type': provider.type,
    } for provider in manager.auth_providers]

    assert providers == [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'id': None,
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
    }]


async def test_auth_manager_from_config_auth_modules(mock_hass):
    """Test get auth modules."""
    with pytest.raises(vol.Invalid):
        manager = await auth.auth_manager_from_config(mock_hass, [{
            'name': 'Test Name',
            'type': 'insecure_example',
            'users': [],
        }, {
            'name': 'Test Name 2',
            'type': 'insecure_example',
            'id': 'another',
            'users': [],
        }], [{
            'name': 'Module 1',
            'type': 'insecure_example',
            'data': [],
        }, {
            'name': 'Invalid config because no data',
            'type': 'insecure_example',
            'id': 'another',
        }])

    manager = await auth.auth_manager_from_config(mock_hass, [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'users': [],
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
        'users': [],
    }], [{
        'name': 'Module 1',
        'type': 'insecure_example',
        'data': [],
    }, {
        'name': 'Module 2',
        'type': 'insecure_example',
        'id': 'another',
        'data': [],
    }])
    providers = [{
            'name': provider.name,
            'type': provider.type,
            'id': provider.id,
        } for provider in manager.auth_providers]
    assert providers == [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'id': None,
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
    }]

    modules = [{
            'name': module.name,
            'type': module.type,
            'id': module.id,
        } for module in manager.auth_mfa_modules]
    assert modules == [{
        'name': 'Module 1',
        'type': 'insecure_example',
        'id': 'insecure_example',
    }, {
        'name': 'Module 2',
        'type': 'insecure_example',
        'id': 'another',
    }]


async def test_create_new_user(hass):
    """Test creating new user."""
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }], [])

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    user = step['result']
    assert user is not None
    assert user.is_owner is False
    assert user.name == 'Test Name'


async def test_login_as_existing_user(mock_hass):
    """Test login as existing user."""
    manager = await auth.auth_manager_from_config(mock_hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }], [])
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add a fake user that we're not going to log in with
    user = MockUser(
        id='mock-user2',
        is_owner=False,
        is_active=False,
        name='Not user',
    ).add_to_auth_manager(manager)
    user.credentials.append(auth_models.Credentials(
        id='mock-id2',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'other-user'},
        is_new=False,
    ))

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    user.credentials.append(auth_models.Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'},
        is_new=False,
    ))

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    user = step['result']
    assert user is not None
    assert user.id == 'mock-user'
    assert user.is_owner is False
    assert user.is_active is False
    assert user.name == 'Paulus'


async def test_linking_user_to_two_auth_providers(hass, hass_storage):
    """Test linking user to two auth providers."""
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
        }]
    }, {
        'type': 'insecure_example',
        'id': 'another-provider',
        'users': [{
            'username': 'another-user',
            'password': 'another-password',
        }]
    }], [])

    step = await manager.login_flow.async_init(('insecure_example', None))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    user = step['result']
    assert user is not None

    step = await manager.login_flow.async_init(
        ('insecure_example', 'another-provider'),
        context={'credential_only': True})
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'another-user',
        'password': 'another-password',
    })
    new_credential = step['result']
    await manager.async_link_user(user, new_credential)
    assert len(user.credentials) == 2


async def test_saving_loading(hass, hass_storage):
    """Test storing and saving data.

    Creates one of each type that we store to test we restore correctly.
    """
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
        }]
    }], [])

    step = await manager.login_flow.async_init(('insecure_example', None))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    user = step['result']
    await manager.async_activate_user(user)
    await manager.async_create_refresh_token(user, CLIENT_ID)

    await flush_store(manager._store._store)

    store2 = auth_store.AuthStore(hass)
    users = await store2.async_get_users()
    assert len(users) == 1
    assert users[0] == user


async def test_cannot_retrieve_expired_access_token(hass):
    """Test that we cannot retrieve expired access tokens."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)
    assert refresh_token.user.id is user.id
    assert refresh_token.client_id == CLIENT_ID

    access_token = manager.async_create_access_token(refresh_token)
    assert (
        await manager.async_validate_access_token(access_token)
        is refresh_token
    )

    with patch('homeassistant.util.dt.utcnow',
               return_value=dt_util.utcnow() -
               auth_const.ACCESS_TOKEN_EXPIRATION - timedelta(seconds=11)):
        access_token = manager.async_create_access_token(refresh_token)

    assert (
        await manager.async_validate_access_token(access_token)
        is None
    )


async def test_generating_system_user(hass):
    """Test that we can add a system user."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = await manager.async_create_system_user('Hass.io')
    token = await manager.async_create_refresh_token(user)
    assert user.system_generated
    assert token is not None
    assert token.client_id is None


async def test_refresh_token_requires_client_for_user(hass):
    """Test that we can add a system user."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    assert user.system_generated is False

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(user)

    token = await manager.async_create_refresh_token(user, CLIENT_ID)
    assert token is not None
    assert token.client_id == CLIENT_ID


async def test_refresh_token_not_requires_client_for_system_user(hass):
    """Test that we can add a system user."""
    manager = await auth.auth_manager_from_config(hass, [], [])
    user = await manager.async_create_system_user('Hass.io')
    assert user.system_generated is True

    with pytest.raises(ValueError):
        await manager.async_create_refresh_token(user, CLIENT_ID)

    token = await manager.async_create_refresh_token(user)
    assert token is not None
    assert token.client_id is None


async def test_cannot_deactive_owner(mock_hass):
    """Test that we cannot deactive the owner."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    owner = MockUser(
        is_owner=True,
    ).add_to_auth_manager(manager)

    with pytest.raises(ValueError):
        await manager.async_deactivate_user(owner)


async def test_remove_refresh_token(mock_hass):
    """Test that we can remove a refresh token."""
    manager = await auth.auth_manager_from_config(mock_hass, [], [])
    user = MockUser().add_to_auth_manager(manager)
    refresh_token = await manager.async_create_refresh_token(user, CLIENT_ID)
    access_token = manager.async_create_access_token(refresh_token)

    await manager.async_remove_refresh_token(refresh_token)

    assert (
        await manager.async_get_refresh_token(refresh_token.id) is None
    )
    assert (
        await manager.async_validate_access_token(access_token) is None
    )


async def test_login_with_auth_module(mock_hass):
    """Test login as existing user with auth module."""
    manager = await auth.auth_manager_from_config(mock_hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }],
    }], [{
        'type': 'insecure_example',
        'data': [{
            'user_id': 'mock-user',
            'pin': 'test-pin'
        }]
    }])
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    user.credentials.append(auth_models.Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'},
        is_new=False,
    ))

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })

    # After auth_provider validated, request auth module input form
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert step['step_id'] == 'mfa'

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'pin': 'invalid-pin',
    })

    # Invalid code error
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert step['step_id'] == 'mfa'
    assert step['errors'] == {'base': 'invalid_code'}

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'pin': 'test-pin',
    })

    # Finally passed, get user
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    user = step['result']
    assert user is not None
    assert user.id == 'mock-user'
    assert user.is_owner is False
    assert user.is_active is False
    assert user.name == 'Paulus'


async def test_login_with_multi_auth_module(mock_hass):
    """Test login as existing user with multiple auth modules."""
    manager = await auth.auth_manager_from_config(mock_hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }],
    }], [{
        'type': 'insecure_example',
        'data': [{
            'user_id': 'mock-user',
            'pin': 'test-pin'
        }]
    }, {
        'type': 'insecure_example',
        'id': 'module2',
        'data': [{
            'user_id': 'mock-user',
            'pin': 'test-pin2'
        }]
    }])
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    user.credentials.append(auth_models.Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'},
        is_new=False,
    ))

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })

    # After auth_provider validated, request select auth module
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert step['step_id'] == 'select_mfa_module'

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'multi_factor_auth_module': 'module2',
    })

    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert step['step_id'] == 'mfa'

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'pin': 'test-pin2',
    })

    # Finally passed, get user
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    user = step['result']
    assert user is not None
    assert user.id == 'mock-user'
    assert user.is_owner is False
    assert user.is_active is False
    assert user.name == 'Paulus'


async def test_auth_module_expired_session(mock_hass):
    """Test login as existing user."""
    manager = await auth.auth_manager_from_config(mock_hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }],
    }], [{
        'type': 'insecure_example',
        'data': [{
            'user_id': 'mock-user',
            'pin': 'test-pin'
        }]
    }])
    mock_hass.auth = manager
    ensure_auth_manager_loaded(manager)

    # Add fake user with credentials for example auth provider.
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
    ).add_to_auth_manager(manager)
    user.credentials.append(auth_models.Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'},
        is_new=False,
    ))

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })

    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert step['step_id'] == 'mfa'

    with patch('homeassistant.util.dt.utcnow',
               return_value=dt_util.utcnow() + SESSION_EXPIRATION):
        step = await manager.login_flow.async_configure(step['flow_id'], {
            'pin': 'test-pin',
        })
        # login flow abort due session timeout
        assert step['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert step['reason'] == 'login_expired'


async def test_enable_mfa_for_user(hass, hass_storage):
    """Test enable mfa module for user."""
    manager = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
        }]
    }], [{
        'type': 'insecure_example',
        'data': [],
    }])

    step = await manager.login_flow.async_init(('insecure_example', None))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    user = step['result']
    assert user is not None

    # new user don't have mfa enabled
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 0

    module = manager.get_auth_mfa_module('insecure_example')
    # mfa module don't have data
    assert bool(module._data) is False

    # test enable mfa for user
    await manager.async_enable_user_mfa(user, 'insecure_example',
                                        {'pin': 'test-pin'})
    assert len(module._data) == 1
    assert module._data[0] == {'user_id': user.id, 'pin': 'test-pin'}

    # test get enabled mfa
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 1
    assert 'insecure_example' in modules

    # re-enable mfa for user will override
    await manager.async_enable_user_mfa(user, 'insecure_example',
                                        {'pin': 'test-pin-new'})
    assert len(module._data) == 1
    assert module._data[0] == {'user_id': user.id, 'pin': 'test-pin-new'}
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 1
    assert 'insecure_example' in modules

    # system user cannot enable mfa
    system_user = await manager.async_create_system_user('system-user')
    with pytest.raises(ValueError):
        await manager.async_enable_user_mfa(system_user, 'insecure_example',
                                            {'pin': 'test-pin'})
    assert len(module._data) == 1
    modules = await manager.async_get_enabled_mfa(system_user)
    assert len(modules) == 0

    # disable mfa for user
    await manager.async_disable_user_mfa(user, 'insecure_example')
    assert bool(module._data) is False

    # test get enabled mfa
    modules = await manager.async_get_enabled_mfa(user)
    assert len(modules) == 0

    # disable mfa for user don't enabled just silent fail
    await manager.async_disable_user_mfa(user, 'insecure_example')
