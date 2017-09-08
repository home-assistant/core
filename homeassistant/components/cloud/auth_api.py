"""Package to offer tools to authenticate with the cloud."""
import json
import logging
import os

from botocore.exceptions import ClientError
from warrant import Cognito
from warrant.exceptions import ForceChangePasswordException

from .const import AUTH_FILE, SERVERS
from .util import get_mode

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
    """Raised when an expired code is encoutered."""


class InvalidCode(CloudError):
    """Raised when an invalid code is submitted."""


class PasswordChangeRequired(CloudError):
    """Raised when a password change is required."""

    # pylint: disable=useless-super-delegation
    def __init__(self, message='Password change required.'):
        """Initialize a password change required error."""
        super().__init__(message)


class UnknownError(CloudError):
    """Raised when an unknown error occurrs."""


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


def load_auth(hass):
    """Load authentication from disk and verify it."""
    info = _read_info(hass)

    if not info:
        return Auth(hass)

    auth = Auth(hass, _cognito(
        hass,
        id_token=info['id_token'],
        access_token=info['access_token'],
        refresh_token=info['refresh_token'],
    ))

    if auth.validate_auth():
        return auth

    return Auth(hass)


def register(hass, email, password):
    """Register a new account."""
    cognito = _cognito(hass, username=email)
    try:
        cognito.register(email, password)
    except ClientError as err:
        raise _map_aws_exception(err)


def confirm_register(hass, confirmation_code, email):
    """Confirm confirmation code after registration."""
    cognito = _cognito(hass, username=email)
    try:
        cognito.confirm_sign_up(confirmation_code, email)
    except ClientError as err:
        raise _map_aws_exception(err)


def forgot_password(hass, email):
    """Initiate forgotten password flow."""
    cognito = _cognito(hass, username=email)
    try:
        cognito.initiate_forgot_password()
    except ClientError as err:
        raise _map_aws_exception(err)


def confirm_forgot_password(hass, confirmation_code, email, new_password):
    """Confirm forgotten password code and change password."""
    cognito = _cognito(hass, username=email)
    try:
        cognito.confirm_forgot_password(confirmation_code, new_password)
    except ClientError as err:
        raise _map_aws_exception(err)


class Auth:
    """Class that holds Cloud authentication."""

    def __init__(self, hass, cognito=None):
        """Initialize Hass cloud info object."""
        self.hass = hass
        self.cognito = cognito
        self.account = None

    @property
    def is_logged_in(self):
        """Return if user is logged in."""
        return self.account is not None

    def validate_auth(self):
        """Validate that the contained auth is valid."""
        try:
            self._refresh_account_info()
        except ClientError as err:
            if err.response['Error']['Code'] != 'NotAuthorizedException':
                _LOGGER.error('Unexpected error verifying auth: %s', err)
                return False

            try:
                self.renew_access_token()
                self._refresh_account_info()
            except ClientError:
                _LOGGER.error('Unable to refresh auth token: %s', err)
                return False

        return True

    def login(self, username, password):
        """Login using a username and password."""
        cognito = _cognito(self.hass, username=username)

        try:
            cognito.authenticate(password=password)
            self.cognito = cognito
            self._refresh_account_info()
            _write_info(self.hass, self)

        except ForceChangePasswordException as err:
            raise PasswordChangeRequired

        except ClientError as err:
            raise _map_aws_exception(err)

    def _refresh_account_info(self):
        """Refresh the account info.

        Raises boto3 exceptions.
        """
        self.account = self.cognito.get_user()

    def renew_access_token(self):
        """Refresh token."""
        try:
            self.cognito.renew_access_token()
            _write_info(self.hass, self)
            return True
        except ClientError as err:
            _LOGGER.error('Error refreshing token: %s', err)
            return False

    def logout(self):
        """Invalidate token."""
        try:
            self.cognito.logout()
            self.account = None
            _write_info(self.hass, self)
        except ClientError as err:
            raise _map_aws_exception(err)


def _read_info(hass):
    """Read auth file."""
    path = hass.config.path(AUTH_FILE)

    if not os.path.isfile(path):
        return None

    with open(path) as file:
        return json.load(file).get(get_mode(hass))


def _write_info(hass, auth):
    """Write auth info for specified mode.

    Pass in None for data to remove authentication for that mode.
    """
    path = hass.config.path(AUTH_FILE)
    mode = get_mode(hass)

    if os.path.isfile(path):
        with open(path) as file:
            content = json.load(file)
    else:
        content = {}

    if auth.is_logged_in:
        content[mode] = {
            'id_token': auth.cognito.id_token,
            'access_token': auth.cognito.access_token,
            'refresh_token': auth.cognito.refresh_token,
        }
    else:
        content.pop(mode, None)

    with open(path, 'wt') as file:
        file.write(json.dumps(content, indent=4, sort_keys=True))


def _cognito(hass, **kwargs):
    """Get the client credentials."""
    mode = get_mode(hass)

    if mode not in SERVERS:
        raise ValueError('Mode {} is not supported.'.format(mode))

    return Cognito(
        SERVERS[mode]['identity_pool_id'],
        SERVERS[mode]['client_id'],
        SERVERS[mode]['region'],
        **kwargs
    )
