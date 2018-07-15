"""Test the example module auth module."""
from homeassistant import auth, data_entry_flow
from homeassistant.auth.mfa_modules import auth_mfa_module_from_config
from homeassistant.auth.models import Credentials
from tests.common import MockUser


async def test_validate(hass):
    """Test validating pin."""
    auth_module = await auth_mfa_module_from_config(hass, {
        'type': 'insecure_example',
        'users': [{'user_id': 'test-user', 'pin': '123456'}]
    })

    result = await auth_module.async_validation(
            'test-user', {'pin': '123456'})
    assert result is True

    result = await auth_module.async_validation(
            'test-user', {'pin': 'invalid'})
    assert result is False

    result = await auth_module.async_validation(
            'invalid-user', {'pin': '123456'})
    assert result is False


async def test_setup_user(hass):
    """Test setup user."""
    auth_module = await auth_mfa_module_from_config(hass, {
        'type': 'insecure_example',
        'users': []
    })

    await auth_module.async_setup_user(
        'test-user', {'pin': '123456'})
    assert len(auth_module._users) == 1

    result = await auth_module.async_validation(
            'test-user', {'pin': '123456'})
    assert result is True


async def test_depose_user(hass):
    """Test despose user."""
    auth_module = await auth_mfa_module_from_config(hass, {
        'type': 'insecure_example',
        'users': [{'user_id': 'test-user', 'pin': '123456'}]
    })
    assert len(auth_module._users) == 1

    await auth_module.async_depose_user('test-user')
    assert len(auth_module._users) == 0


async def test_login(hass):
    """Test login flow with auth module."""
    hass.auth = await auth.auth_manager_from_config(hass, [{
        'type': 'insecure_example',
        'users': [{'username': 'test-user', 'password': 'test-pass'}],
    }], [{
        'type': 'insecure_example',
        'users': [{'user_id': 'mock-user', 'pin': '123456'}]
    }])
    user = MockUser(
        id='mock-user',
        is_owner=False,
        is_active=False,
        name='Paulus',
        mfa_modules=['insecure_example']
    ).add_to_auth_manager(hass.auth)
    await hass.auth.async_link_user(user, Credentials(
        id='mock-id',
        auth_provider_type='insecure_example',
        auth_provider_id=None,
        data={'username': 'test-user'},
        is_new=False,
    ))

    provider = hass.auth.auth_providers[0]
    flow = await provider.async_login_flow()

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
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'mfa'
    assert result['data_schema'].schema.get('pin') == str

    result = await flow.async_step_mfa({'pin': 'invalid-code'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['errors']['base'] == 'invalid_auth'

    result = await flow.async_step_mfa({'pin': '123456'})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['data']['username'] == 'test-user'
