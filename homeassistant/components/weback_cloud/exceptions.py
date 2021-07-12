"""Custom Exceptions for Weback Cloud integration."""
from homeassistant.exceptions import HomeAssistantError


class InvalidCredentials(HomeAssistantError):
    """Error to indicate authentication issues."""

    def __init__(self, *args):
        """Instantiate InvalidCredentials exception."""
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        """Return error messages."""
        if self.message:
            return f"Cannot connect: {self.message}"
        else:
            return "Cannot connect due to an unknown error"
