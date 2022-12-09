"""Exceptions for Twinkly."""


class TwinklyError(ValueError):
    """Error from the API."""

    def __init__(self, message: str, response=None) -> None:
        """Initiate the exception."""
        self.message = message
        self.response = response
