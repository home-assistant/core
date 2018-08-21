from hangups import CredentialsPrompt, RefreshTokenCache, GoogleAuthError


class Google2FAError(GoogleAuthError):
    """A Google authentication request failed."""


class HangoutsCredentials(CredentialsPrompt):

    def __init__(self, email, password, pin=None):
        self._email = email
        self._password = password
        self._pin = pin

    def get_email(self):
        return self._email

    def get_password(self):
        return self._password

    def get_verification_code(self):
        if self._pin is None:
            raise Google2FAError()
        return self._pin

    def set_verification_code(self, pin):
        self._pin = pin


class HangoutsRefreshToken(RefreshTokenCache):

    def __init__(self, token):
        super().__init__("")
        self._token = token

    def get(self):
        return self._token

    def set(self, refresh_token):
        self._token = refresh_token
