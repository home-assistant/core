class MazdaConfigException(Exception):  # noqa: D100
    """Raised when Mazda API client is configured incorrectly."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaAuthenticationException(Exception):
    """Raised when email address or password are invalid during authentication."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaAccountLockedException(Exception):
    """Raised when account is locked from too many login attempts."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaTokenExpiredException(Exception):
    """Raised when server reports that the access token has expired."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaAPIEncryptionException(Exception):
    """Raised when server reports that the request is not encrypted properly."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaException(Exception):
    """Raised when an unknown error occurs during API interaction."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaLoginFailedException(Exception):
    """Raised when login fails for an unknown reason."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status


class MazdaRequestInProgressException(Exception):
    """Raised when a request fails because another request is already in progress."""

    def __init__(self, status):
        """Initialize exception."""
        super().__init__(status)
        self.status = status
