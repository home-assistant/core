"""Utils needed for Google Hangouts."""

from hangups import CredentialsPrompt, GoogleAuthError, RefreshTokenCache


class Google2FAError(GoogleAuthError):
    """A Google authentication request failed."""


class HangoutsCredentials(CredentialsPrompt):
    """Google account credentials.

    This implementation gets the user data as params.
    """

    def __init__(self, email, password, pin=None):
        """Google account credentials.

        :param email: Google account email address.
        :param password: Google account password.
        :param pin: Google account verification code.
        """
        self._email = email
        self._password = password
        self._pin = pin

    def get_email(self):
        """Return email.

        :return: Google account email address.
        """
        return self._email

    def get_password(self):
        """Return password.

        :return: Google account password.
        """
        return self._password

    def get_verification_code(self):
        """Return the verification code.

        :return: Google account verification code.
        """
        if self._pin is None:
            raise Google2FAError()
        return self._pin

    def set_verification_code(self, pin):
        """Set the verification code.

        :param pin: Google account verification code.
        """
        self._pin = pin


class HangoutsRefreshToken(RefreshTokenCache):
    """Memory-based cache for refresh token."""

    def __init__(self, token):
        """Memory-based cache for refresh token.

        :param token: Initial refresh token.
        """
        super().__init__("")
        self._token = token

    def get(self):
        """Get cached refresh token.

        :return: Cached refresh token.
        """
        return self._token

    def set(self, refresh_token):
        """Cache a refresh token.

        :param refresh_token: Refresh token to cache.
        """
        self._token = refresh_token
