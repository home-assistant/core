"""Tests for the tools to communicate with the cloud."""
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
import pytest

from homeassistant.components.cloud import auth_api


@pytest.fixture
def mock_cognito():
    """Mock warrant."""
    with patch('homeassistant.components.cloud.auth_api._cognito') as mock_cog:
        yield mock_cog()


def aws_error(code, message='Unknown', operation_name='fake_operation_name'):
    """Generate AWS error response."""
    response = {
        'Error': {
            'Code': code,
            'Message': message
        }
    }
    return ClientError(response, operation_name)


def test_login_invalid_auth(mock_cognito):
    """Test trying to login with invalid credentials."""
    cloud = MagicMock(is_logged_in=False)
    mock_cognito.authenticate.side_effect = aws_error('NotAuthorizedException')

    with pytest.raises(auth_api.Unauthenticated):
        auth_api.login(cloud, 'user', 'pass')

    assert len(cloud.write_user_info.mock_calls) == 0


def test_login_user_not_found(mock_cognito):
    """Test trying to login with invalid credentials."""
    cloud = MagicMock(is_logged_in=False)
    mock_cognito.authenticate.side_effect = aws_error('UserNotFoundException')

    with pytest.raises(auth_api.UserNotFound):
        auth_api.login(cloud, 'user', 'pass')

    assert len(cloud.write_user_info.mock_calls) == 0


def test_login_user_not_confirmed(mock_cognito):
    """Test trying to login without confirming account."""
    cloud = MagicMock(is_logged_in=False)
    mock_cognito.authenticate.side_effect = \
        aws_error('UserNotConfirmedException')

    with pytest.raises(auth_api.UserNotConfirmed):
        auth_api.login(cloud, 'user', 'pass')

    assert len(cloud.write_user_info.mock_calls) == 0


def test_login(mock_cognito):
    """Test trying to login without confirming account."""
    cloud = MagicMock(is_logged_in=False)
    mock_cognito.id_token = 'test_id_token'
    mock_cognito.access_token = 'test_access_token'
    mock_cognito.refresh_token = 'test_refresh_token'

    auth_api.login(cloud, 'user', 'pass')

    assert len(mock_cognito.authenticate.mock_calls) == 1
    assert cloud.id_token == 'test_id_token'
    assert cloud.access_token == 'test_access_token'
    assert cloud.refresh_token == 'test_refresh_token'
    assert len(cloud.write_user_info.mock_calls) == 1


def test_register(mock_cognito):
    """Test registering an account."""
    cloud = MagicMock()
    cloud = MagicMock()
    auth_api.register(cloud, 'email@home-assistant.io', 'password')
    assert len(mock_cognito.register.mock_calls) == 1
    result_user, result_password = mock_cognito.register.mock_calls[0][1]
    assert result_user == 'email@home-assistant.io'
    assert result_password == 'password'


def test_register_fails(mock_cognito):
    """Test registering an account."""
    cloud = MagicMock()
    mock_cognito.register.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.register(cloud, 'email@home-assistant.io', 'password')


def test_confirm_register(mock_cognito):
    """Test confirming a registration of an account."""
    cloud = MagicMock()
    auth_api.confirm_register(cloud, '123456', 'email@home-assistant.io')
    assert len(mock_cognito.confirm_sign_up.mock_calls) == 1
    result_code, result_user = mock_cognito.confirm_sign_up.mock_calls[0][1]
    assert result_user == 'email@home-assistant.io'
    assert result_code == '123456'


def test_confirm_register_fails(mock_cognito):
    """Test an error during confirmation of an account."""
    cloud = MagicMock()
    mock_cognito.confirm_sign_up.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.confirm_register(cloud, '123456', 'email@home-assistant.io')


def test_resend_email_confirm(mock_cognito):
    """Test starting forgot password flow."""
    cloud = MagicMock()
    auth_api.resend_email_confirm(cloud, 'email@home-assistant.io')
    assert len(mock_cognito.client.resend_confirmation_code.mock_calls) == 1


def test_resend_email_confirm_fails(mock_cognito):
    """Test failure when starting forgot password flow."""
    cloud = MagicMock()
    mock_cognito.client.resend_confirmation_code.side_effect = \
        aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.resend_email_confirm(cloud, 'email@home-assistant.io')


def test_forgot_password(mock_cognito):
    """Test starting forgot password flow."""
    cloud = MagicMock()
    auth_api.forgot_password(cloud, 'email@home-assistant.io')
    assert len(mock_cognito.initiate_forgot_password.mock_calls) == 1


def test_forgot_password_fails(mock_cognito):
    """Test failure when starting forgot password flow."""
    cloud = MagicMock()
    mock_cognito.initiate_forgot_password.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.forgot_password(cloud, 'email@home-assistant.io')


def test_confirm_forgot_password(mock_cognito):
    """Test confirming forgot password."""
    cloud = MagicMock()
    auth_api.confirm_forgot_password(
        cloud, '123456', 'email@home-assistant.io', 'new password')
    assert len(mock_cognito.confirm_forgot_password.mock_calls) == 1
    result_code, result_password = \
        mock_cognito.confirm_forgot_password.mock_calls[0][1]
    assert result_code == '123456'
    assert result_password == 'new password'


def test_confirm_forgot_password_fails(mock_cognito):
    """Test failure when confirming forgot password."""
    cloud = MagicMock()
    mock_cognito.confirm_forgot_password.side_effect = aws_error('SomeError')
    with pytest.raises(auth_api.CloudError):
        auth_api.confirm_forgot_password(
            cloud, '123456', 'email@home-assistant.io', 'new password')


def test_check_token_writes_new_token_on_refresh(mock_cognito):
    """Test check_token writes new token if refreshed."""
    cloud = MagicMock()
    mock_cognito.check_token.return_value = True
    mock_cognito.id_token = 'new id token'
    mock_cognito.access_token = 'new access token'

    auth_api.check_token(cloud)

    assert len(mock_cognito.check_token.mock_calls) == 1
    assert cloud.id_token == 'new id token'
    assert cloud.access_token == 'new access token'
    assert len(cloud.write_user_info.mock_calls) == 1


def test_check_token_does_not_write_existing_token(mock_cognito):
    """Test check_token won't write new token if still valid."""
    cloud = MagicMock()
    mock_cognito.check_token.return_value = False

    auth_api.check_token(cloud)

    assert len(mock_cognito.check_token.mock_calls) == 1
    assert cloud.id_token != mock_cognito.id_token
    assert cloud.access_token != mock_cognito.access_token
    assert len(cloud.write_user_info.mock_calls) == 0


def test_check_token_raises(mock_cognito):
    """Test we raise correct error."""
    cloud = MagicMock()
    mock_cognito.check_token.side_effect = aws_error('SomeError')

    with pytest.raises(auth_api.CloudError):
        auth_api.check_token(cloud)

    assert len(mock_cognito.check_token.mock_calls) == 1
    assert cloud.id_token != mock_cognito.id_token
    assert cloud.access_token != mock_cognito.access_token
    assert len(cloud.write_user_info.mock_calls) == 0
