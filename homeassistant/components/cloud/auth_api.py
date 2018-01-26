"""Package to communicate with the authentication API."""
import logging

_LOGGER = logging.getLogger(__name__)


class CloudError(Exception):
    """Base class for cloud related errors."""


class Unauthenticated(CloudError):
    """Raised when authentication failed."""


class UserNotFound(CloudError):
    """Raised when a user is not found."""


class UserNotConfirmed(CloudError):
    """Raised when a user has not confirmed email yet."""


class ExpiredCode(CloudError):
    """Raised when an expired code is encountered."""


class InvalidCode(CloudError):
    """Raised when an invalid code is submitted."""


class PasswordChangeRequired(CloudError):
    """Raised when a password change is required."""

    def __init__(self, message='Password change required.'):
        """Initialize a password change required error."""
        super().__init__(message)


class UnknownError(CloudError):
    """Raised when an unknown error occurs."""


AWS_EXCEPTIONS = {
    'UserNotFoundException': UserNotFound,
    'NotAuthorizedException': Unauthenticated,
    'ExpiredCodeException': ExpiredCode,
    'UserNotConfirmedException': UserNotConfirmed,
    'PasswordResetRequiredException': PasswordChangeRequired,
    'CodeMismatchException': InvalidCode,
}


def _map_aws_exception(err):
    """Map AWS exception to our exceptions."""
    ex = AWS_EXCEPTIONS.get(err.response['Error']['Code'], UnknownError)
    return ex(err.response['Error']['Message'])


def register(cloud, email, password):
    """Register a new account."""
    from botocore.exceptions import ClientError

    cognito = _cognito(cloud)
    # Workaround for bug in Warrant. PR with fix:
    # https://github.com/capless/warrant/pull/82
    cognito.add_base_attributes()
    try:
        cognito.register(email, password)
    except ClientError as err:
        raise _map_aws_exception(err)


def confirm_register(cloud, confirmation_code, email):
    """Confirm confirmation code after registration."""
    from botocore.exceptions import ClientError

    cognito = _cognito(cloud)
    try:
        cognito.confirm_sign_up(confirmation_code, email)
    except ClientError as err:
        raise _map_aws_exception(err)


def resend_email_confirm(cloud, email):
    """Resend email confirmation."""
    from botocore.exceptions import ClientError

    cognito = _cognito(cloud, username=email)

    try:
        cognito.client.resend_confirmation_code(
            Username=email,
            ClientId=cognito.client_id
        )
    except ClientError as err:
        raise _map_aws_exception(err)


def forgot_password(cloud, email):
    """Initialize forgotten password flow."""
    from botocore.exceptions import ClientError

    cognito = _cognito(cloud, username=email)

    try:
        cognito.initiate_forgot_password()
    except ClientError as err:
        raise _map_aws_exception(err)


def confirm_forgot_password(cloud, confirmation_code, email, new_password):
    """Confirm forgotten password code and change password."""
    from botocore.exceptions import ClientError

    cognito = _cognito(cloud, username=email)

    try:
        cognito.confirm_forgot_password(confirmation_code, new_password)
    except ClientError as err:
        raise _map_aws_exception(err)


def login(cloud, email, password):
    """Log user in and fetch certificate."""
    cognito = _authenticate(cloud, email, password)
    cloud.id_token = cognito.id_token
    cloud.access_token = cognito.access_token
    cloud.refresh_token = cognito.refresh_token
    cloud.write_user_info()


def check_token(cloud):
    """Check that the token is valid and verify if needed."""
    from botocore.exceptions import ClientError

    cognito = _cognito(
        cloud,
        access_token=cloud.access_token,
        refresh_token=cloud.refresh_token)

    try:
        if cognito.check_token():
            cloud.id_token = cognito.id_token
            cloud.access_token = cognito.access_token
            cloud.write_user_info()
    except ClientError as err:
        raise _map_aws_exception(err)


def _authenticate(cloud, email, password):
    """Log in and return an authenticated Cognito instance."""
    from botocore.exceptions import ClientError
    from warrant.exceptions import ForceChangePasswordException

    assert not cloud.is_logged_in, 'Cannot login if already logged in.'

    cognito = _cognito(cloud, username=email)

    try:
        cognito.authenticate(password=password)
        return cognito

    except ForceChangePasswordException as err:
        raise PasswordChangeRequired

    except ClientError as err:
        raise _map_aws_exception(err)


def _cognito(cloud, **kwargs):
    """Get the client credentials."""
    import botocore
    import boto3
    from warrant import Cognito

    cognito = Cognito(
        user_pool_id=cloud.user_pool_id,
        client_id=cloud.cognito_client_id,
        user_pool_region=cloud.region,
        **kwargs
    )
    cognito.client = boto3.client(
        'cognito-idp',
        region_name=cloud.region,
        config=botocore.config.Config(
            signature_version=botocore.UNSIGNED
        )
    )
    return cognito
