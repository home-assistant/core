"""Test the Home Assistant local auth provider."""
import pytest

from homeassistant import data_entry_flow
from homeassistant.auth.providers import homeassistant as hass_auth


@pytest.fixture
def data(hass):
    """Create a loaded data class."""
    data = hass_auth.Data(hass)
    hass.loop.run_until_complete(data.async_load())
    return data


async def test_adding_user(data, hass):
    """Test adding a user."""
    data.add_user('test-user', 'test-pass')
    data.validate_login('test-user', 'test-pass')


async def test_adding_user_duplicate_username(data, hass):
    """Test adding a user."""
    data.add_user('test-user', 'test-pass')
    with pytest.raises(hass_auth.InvalidUser):
        data.add_user('test-user', 'other-pass')


async def test_validating_password_invalid_user(data, hass):
    """Test validating an invalid user."""
    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('non-existing', 'pw')


async def test_validating_password_invalid_password(data, hass):
    """Test validating an invalid user."""
    data.add_user('test-user', 'test-pass')

    with pytest.raises(hass_auth.InvalidAuth):
        data.validate_login('test-user', 'invalid-pass')


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


async def test_saving_loading(data, hass):
    """Test saving and loading JSON."""
    data.add_user('test-user', 'test-pass')
    data.add_user('second-user', 'second-pass')
    await data.async_save()

    data = hass_auth.Data(hass)
    await data.async_load()
    data.validate_login('test-user', 'test-pass')
    data.validate_login('second-user', 'second-pass')
