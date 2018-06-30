"""Test the Home Assistant local auth provider."""
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.auth_providers import homeassistant as hass_auth

MOCK_SECRET = 'secret'
MOCK_CODE = '123456'


@pytest.fixture
def data(hass):
    """Create a loaded data class."""
    data = hass_auth.Data(hass)
    hass.loop.run_until_complete(data.async_load())
    return data


@pytest.fixture
def data_2fa(hass):
    """Create a loaded data class."""
    data = hass_auth.Data(hass, True)
    hass.loop.run_until_complete(data.async_load())
    return data


async def test_adding_user(data, hass):
    """Test adding a user."""
    data.add_user('test-user', 'test-pass')
    data.validate_login('test-user', 'test-pass')


async def test_adding_user_2fa(data_2fa, hass):
    """Test adding a user with 2fa enabled."""
    with patch('pyotp.random_base32', return_value=MOCK_SECRET):
        secret = data_2fa.add_user('test-user', 'test-pass')
        assert secret is MOCK_SECRET
    assert secret is not None

    try:
        data_2fa.validate_login('test-user', 'test-pass')
        pytest.fail('Shall raise Request2FA')
    except hass_auth.Request2FA as request2fa:
        session_token = request2fa.session_token
        assert session_token is not None

        with patch('pyotp.TOTP.verify', return_value=True):
            data_2fa.validate_2fa(session_token, MOCK_CODE)


async def test_adding_user_duplicate_username(data, hass):
    """Test adding a user with duplicate username."""
    data.add_user('test-user', 'test-pass')
    with pytest.raises(hass_auth.InvalidUser):
        data.add_user('test-user', 'other-pass')


async def test_validating_password_invalid_user(data, hass):
    """Test validating an invalid user."""
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('non-existing', 'pw')


async def test_validating_password_invalid_password(data, hass):
    """Test validating an invalid password."""
    data.add_user('test-user', 'test-pass')

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('test-user', 'invalid-pass')


async def test_validating_2fa_invalid_code(data_2fa, hass):
    """Test validating an invalid 2fa code."""
    with patch('pyotp.random_base32', return_value=MOCK_SECRET):
        data_2fa.add_user('test-user', 'test-pass')

    try:
        data_2fa.validate_login('test-user', 'test-pass')
        pytest.fail('Shall raise Request2FA')
    except hass_auth.Request2FA as request2fa:
        session_token = request2fa.session_token

        with patch('pyotp.TOTP.verify', return_value=False):
            with pytest.raises(hass_auth.InvalidAuth):
                data_2fa.validate_2fa(session_token, MOCK_CODE)


async def test_validating_2fa_invalid_session(data_2fa, hass):
    """Test validating an 2fa code with invalid session_token."""
    with patch('pyotp.random_base32', return_value=MOCK_SECRET):
        data_2fa.add_user('test-user', 'test-pass')

    try:
        data_2fa.validate_login('test-user', 'test-pass')
        pytest.fail('Shall raise Request2FA')
    except hass_auth.Request2FA:
        with patch('pyotp.TOTP.verify', return_value=True):
            with pytest.raises(hass_auth.InvalidAuth):
                data_2fa.validate_2fa('invalid-session', MOCK_CODE)


async def test_changing_password(data, hass):
    """Test adding a user."""
    user = 'test-user'
    data.add_user(user, 'test-pass')
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
    data.add_user('test-user', 'test-pass')
    await data.async_save()

    provider = hass_auth.HassAuthProvider(hass, None, {})
    flow = hass_auth.LoginFlow(provider)
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


async def test_login_flow_validates_2fa(data_2fa, hass):
    """Test login flow with 2fa enabled."""
    data_2fa.add_user('test-user', 'test-pass')
    await data_2fa.async_save()

    provider = hass_auth.HassAuthProvider(hass, None, {'enable_2fa': True})
    flow = hass_auth.LoginFlow(provider)
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
    assert result['errors']['base'] == 'request_2fa'

    with patch('pyotp.TOTP.verify', return_value=False):
        result = await flow.async_step_init({
            'code': 'invalid-code',
        })
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['errors']['base'] == 'invalid_auth'

    with patch('pyotp.TOTP.verify', return_value=True):
        result = await flow.async_step_init({
            'code': MOCK_CODE,
        })
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['data']['username'] == 'test-user'


async def test_saving_loading(data, hass):
    """Test saving and loading JSON."""
    data.add_user('test-user', 'test-pass')
    data.add_user('second-user', 'second-pass')
    await data.async_save()

    data = hass_auth.Data(hass)
    await data.async_load()
    data.validate_login('test-user', 'test-pass')
    data.validate_login('second-user', 'second-pass')
