"""Tests for the tools to communicate with the cloud."""
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
import pytest

from homeassistant.components.cloud import DOMAIN, auth_api


MOCK_AUTH = {
    "id_token": "fake_id_token",
    "access_token": "fake_access_token",
    "refresh_token": "fake_refresh_token",
}


@pytest.fixture
def cloud_hass(hass):
    """Fixture to return a hass instance with cloud mode set."""
    hass.data[DOMAIN] = {'mode': 'development'}
    return hass


@pytest.fixture
def mock_write():
    """Mock reading authentication."""
    with patch.object(auth_api, '_write_info') as mock:
        yield mock


@pytest.fixture
def mock_read():
    """Mock writing authentication."""
    with patch.object(auth_api, '_read_info') as mock:
        yield mock


@pytest.fixture
def mock_cognito():
    """Mock warrant."""
    with patch('homeassistant.components.cloud.auth_api._cognito') as mock_cog:
        yield mock_cog()


@pytest.fixture
def mock_auth():
    """Mock warrant."""
    with patch('homeassistant.components.cloud.auth_api.Auth') as mock_auth:
        yield mock_auth()


def aws_error(code, message='Unknown', operation_name='fake_operation_name'):
    """Generate AWS error response."""
    response = {
        'Error': {
            'Code': code,
            'Message': message
        }
    }
    return ClientError(response, operation_name)


def test_load_auth_with_no_stored_auth(cloud_hass, mock_read):
    """Test loading authentication with no stored auth."""
    mock_read.return_value = None
    auth = auth_api.load_auth(cloud_hass)
    assert auth.cognito is None


def test_load_auth_with_invalid_auth(cloud_hass, mock_read, mock_cognito):
    """Test calling load_auth when auth is no longer valid."""
    mock_cognito.get_user.side_effect = aws_error('SomeError')
    auth = auth_api.load_auth(cloud_hass)

    assert auth.cognito is None


def test_load_auth_with_valid_auth(cloud_hass, mock_read, mock_cognito):
    """Test calling load_auth when valid auth."""
    auth = auth_api.load_auth(cloud_hass)

    assert auth.cognito is not None


def test_auth_properties():
    """Test Auth class properties."""
    auth = auth_api.Auth(None, None)
    assert not auth.is_logged_in
    auth.account = {}
    assert auth.is_logged_in


def test_auth_validate_auth_verification_fails(mock_cognito):
    """Test validate authentication with verify request failing."""
    mock_cognito.get_user.side_effect = aws_error('UserNotFoundException')

    auth = auth_api.Auth(None, mock_cognito)
    assert auth.validate_auth() is False


def test_auth_validate_auth_token_refresh_needed_fails(mock_cognito):
    """Test validate authentication with refresh needed which gets 401."""
    mock_cognito.get_user.side_effect = aws_error('NotAuthorizedException')
    mock_cognito.renew_access_token.side_effect = \
        aws_error('NotAuthorizedException')

    auth = auth_api.Auth(None, mock_cognito)
    assert auth.validate_auth() is False


def test_auth_validate_auth_token_refresh_needed_succeeds(mock_write,
                                                          mock_cognito):
    """Test validate authentication with refresh."""
    mock_cognito.get_user.side_effect = [
        aws_error('NotAuthorizedException'),
        MagicMock(email='hello@home-assistant.io')
    ]

    auth = auth_api.Auth(None, mock_cognito)
    assert auth.validate_auth() is True
    assert len(mock_write.mock_calls) == 1


def test_auth_login_invalid_auth(mock_cognito, mock_write):
    """Test trying to login with invalid credentials."""
    mock_cognito.authenticate.side_effect = aws_error('NotAuthorizedException')
    auth = auth_api.Auth(None, None)
    with pytest.raises(auth_api.Unauthenticated):
        auth.login('user', 'pass')

    assert not auth.is_logged_in
    assert len(mock_cognito.get_user.mock_calls) == 0
    assert len(mock_write.mock_calls) == 0


def test_auth_login_user_not_found(mock_cognito, mock_write):
    """Test trying to login with invalid credentials."""
    mock_cognito.authenticate.side_effect = aws_error('UserNotFoundException')
    auth = auth_api.Auth(None, None)
    with pytest.raises(auth_api.UserNotFound):
        auth.login('user', 'pass')

    assert not auth.is_logged_in
    assert len(mock_cognito.get_user.mock_calls) == 0
    assert len(mock_write.mock_calls) == 0


def test_auth_login_user_not_confirmed(mock_cognito, mock_write):
    """Test trying to login without confirming account."""
    mock_cognito.authenticate.side_effect = \
        aws_error('UserNotConfirmedException')
    auth = auth_api.Auth(None, None)
    with pytest.raises(auth_api.UserNotConfirmed):
        auth.login('user', 'pass')

    assert not auth.is_logged_in
    assert len(mock_cognito.get_user.mock_calls) == 0
    assert len(mock_write.mock_calls) == 0


def test_auth_login(cloud_hass, mock_cognito, mock_write):
    """Test trying to login without confirming account."""
    mock_cognito.get_user.return_value = \
        MagicMock(email='hello@home-assistant.io')
    auth = auth_api.Auth(cloud_hass, None)
    auth.login('user', 'pass')
    assert auth.is_logged_in
    assert len(mock_cognito.authenticate.mock_calls) == 1
    assert len(mock_write.mock_calls) == 1
    result_hass, result_auth = mock_write.mock_calls[0][1]
    assert result_hass is cloud_hass
    assert result_auth is auth


def test_auth_renew_access_token(mock_write, mock_cognito):
    """Test renewing an access token."""
    auth = auth_api.Auth(None, mock_cognito)
    assert auth.renew_access_token()
    assert len(mock_write.mock_calls) == 1


def test_auth_renew_access_token_fails(mock_write, mock_cognito):
    """Test failing to renew an access token."""
    mock_cognito.renew_access_token.side_effect = aws_error('SomeError')
    auth = auth_api.Auth(None, mock_cognito)
    assert not auth.renew_access_token()
    assert len(mock_write.mock_calls) == 0


def test_auth_logout(mock_write, mock_cognito):
    """Test renewing an access token."""
    auth = auth_api.Auth(None, mock_cognito)
    auth.account = MagicMock()
    auth.logout()
    assert auth.account is None
    assert len(mock_write.mock_calls) == 1


def test_auth_logout_fails(mock_write, mock_cognito):
    """Test error while logging out."""
    mock_cognito.logout.side_effect = aws_error('SomeError')
    auth = auth_api.Auth(None, mock_cognito)
    auth.account = MagicMock()
    with pytest.raises(auth_api.CloudError):
        auth.logout()
    assert auth.account is not None
    assert len(mock_write.mock_calls) == 0


def test_register(mock_cognito):
    """Test registering an account."""
    auth_api.register(None, 'email@home-assistant.io', 'password')
    assert len(mock_cognito.register.mock_calls) == 1
    result_email, result_password = mock_cognito.register.mock_calls[0][1]
    assert result_email == 'email@home-assistant.io'
    assert result_password == 'password'


def test_register_fails(mock_cognito):
    """Test registering an account."""
    mock_cognito.register.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.register(None, 'email@home-assistant.io', 'password')


def test_confirm_register(mock_cognito):
    """Test confirming a registration of an account."""
    auth_api.confirm_register(None, '123456', 'email@home-assistant.io')
    assert len(mock_cognito.confirm_sign_up.mock_calls) == 1
    result_code, result_email = mock_cognito.confirm_sign_up.mock_calls[0][1]
    assert result_email == 'email@home-assistant.io'
    assert result_code == '123456'


def test_confirm_register_fails(mock_cognito):
    """Test an error during confirmation of an account."""
    mock_cognito.confirm_sign_up.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.confirm_register(None, '123456', 'email@home-assistant.io')


def test_forgot_password(mock_cognito):
    """Test starting forgot password flow."""
    auth_api.forgot_password(None, 'email@home-assistant.io')
    assert len(mock_cognito.initiate_forgot_password.mock_calls) == 1


def test_forgot_password_fails(mock_cognito):
    """Test failure when starting forgot password flow."""
    mock_cognito.initiate_forgot_password.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.forgot_password(None, 'email@home-assistant.io')


def test_confirm_forgot_password(mock_cognito):
    """Test confirming forgot password."""
    auth_api.confirm_forgot_password(
        None, '123456', 'email@home-assistant.io', 'new password')
    assert len(mock_cognito.confirm_forgot_password.mock_calls) == 1
    result_code, result_password = \
        mock_cognito.confirm_forgot_password.mock_calls[0][1]
    assert result_code == '123456'
    assert result_password == 'new password'


def test_confirm_forgot_password_fails(mock_cognito):
    """Test failure when confirming forgot password."""
    mock_cognito.confirm_forgot_password.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.confirm_forgot_password(
            None, '123456', 'email@home-assistant.io', 'new password')
