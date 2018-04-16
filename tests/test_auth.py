"""Tests for the Home Assistant auth module."""

from homeassistant import auth, data_entry_flow


async def test_auth_manager_from_config_validates_config_and_id():
    """Test get auth providers."""
    manager = await auth.auth_manager_from_config(None, [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'users': [],
    }, {
        'name': 'Invalid config because no users',
        'type': 'insecure_example',
        'id': 'invalid_config',
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
        'users': [],
    }, {
        'name': 'Wrong because duplicate ID',
        'type': 'insecure_example',
        'id': 'another',
        'users': [],
    }])

    assert manager.async_auth_providers() == [{
        'name': 'Test Name',
        'type': 'insecure_example',
        'id': None,
    }, {
        'name': 'Test Name 2',
        'type': 'insecure_example',
        'id': 'another',
    }]


async def test_create_new_user():
    """Test creating new user."""
    manager = await auth.auth_manager_from_config(None, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }])

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    credentials = step['result']
    user = await manager.async_get_or_create_user(credentials)
    assert user is not None
    assert user.is_owner is True
    assert user.name == 'Test Name'


async def test_login_as_existing_user():
    """Test login as existing user."""
    manager = await auth.auth_manager_from_config(None, [{
        'type': 'insecure_example',
        'users': [{
            'username': 'test-user',
            'password': 'test-pass',
            'name': 'Test Name'
        }]
    }])

    # Add fake user with credentials for example auth provider.
    user = auth.User(id='mock-user')
    user.credentials.append(auth.Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'}
    ))
    manager._store.users = [user]

    step = await manager.login_flow.async_init(('insecure_example', None))
    assert step['type'] == data_entry_flow.RESULT_TYPE_FORM

    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    assert step['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    credentials = step['result']
    user = await manager.async_get_or_create_user(credentials)
    assert user is not None
    assert user.id == 'mock-user'
    assert user.is_owner is False
    assert user.name is None


async def test_linking_user_to_two_auth_providers():
    """Test linking user to two auth providers."""
    manager = await auth.auth_manager_from_config(None, [{
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
    }])

    step = await manager.login_flow.async_init(('insecure_example', None))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'test-user',
        'password': 'test-pass',
    })
    user = await manager.async_get_or_create_user(step['result'])
    assert user is not None

    step = await manager.login_flow.async_init(('insecure_example', 'another-provider'))
    step = await manager.login_flow.async_configure(step['flow_id'], {
        'username': 'another-user',
        'password': 'another-password',
    })
    await manager.link_user(user, step['result'])
    assert len(user.credentials) == 2
