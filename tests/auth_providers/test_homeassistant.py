"""Test the Home Assistant local auth provider."""
from unittest.mock import patch, mock_open

import pytest

from homeassistant import data_entry_flow
from homeassistant.auth_providers import homeassistant as hass_auth


MOCK_PATH = '/bla/users.json'
JSON__OPEN_PATH = 'homeassistant.util.json.open'


def test_initialize_empty_config_file_not_found():
    """Test that we initialize an empty config."""
    with patch('homeassistant.util.json.open', side_effect=FileNotFoundError):
        data = hass_auth.load_data(MOCK_PATH)

    assert data is not None


def test_adding_user():
    """Test adding a user."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')
    data.validate_login('test-user', 'test-pass')


def test_adding_user_duplicate_username():
    """Test adding a user."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')
    with pytest.raises(hass_auth.InvalidUser):
        data.add_user('test-user', 'other-pass')


def test_validating_password_invalid_user():
    """Test validating an invalid user."""
    data = hass_auth.Data(MOCK_PATH, None)

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('non-existing', 'pw')


def test_validating_password_invalid_password():
    """Test validating an invalid user."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('test-user', 'invalid-pass')


def test_changing_password():
    """Test adding a user."""
    user = 'test-user'
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user(user, 'test-pass')
    data.change_password(user, 'new-pass')

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login(user, 'test-pass')

    data.validate_login(user, 'new-pass')


def test_changing_password_raises_invalid_user():
    """Test that we initialize an empty config."""
    data = hass_auth.Data(MOCK_PATH, None)

    with pytest.raises(hass_auth.InvalidUser):
        data.change_password('non-existing', 'pw')


async def test_login_flow_validates(hass):
    """Test login flow."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')

    provider = hass_auth.HassAuthProvider(hass, None, {})
    flow = hass_auth.LoginFlow(provider)
    result = await flow.async_step_init()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM

    with patch.object(provider, '_auth_data', return_value=data):
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


async def test_saving_loading(hass):
    """Test saving and loading JSON."""
    data = hass_auth.Data(MOCK_PATH, None)
    data.add_user('test-user', 'test-pass')
    data.add_user('second-user', 'second-pass')

    with patch(JSON__OPEN_PATH, mock_open(), create=True) as mock_write:
        await hass.async_add_job(data.save)

    # Mock open calls are: open file, context enter, write, context leave
    written = mock_write.mock_calls[2][1][0]

    with patch('os.path.isfile', return_value=True), \
            patch(JSON__OPEN_PATH, mock_open(read_data=written), create=True):
        await hass.async_add_job(hass_auth.load_data, MOCK_PATH)

    data.validate_login('test-user', 'test-pass')
    data.validate_login('second-user', 'second-pass')
