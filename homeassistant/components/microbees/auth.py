"""auth class for the microBees integration."""


class MicroBeesAuth:
    """Abstract class to make authenticated requests."""

    def __init__(self, token: str) -> None:
        """Initialize the AbstractAuth."""
        self.token = token

    # @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return self.token
