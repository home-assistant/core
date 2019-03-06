"""Helper classes for Google Assistant integration."""
from homeassistant.core import Context


class SmartHomeError(Exception):
    """Google Assistant Smart Home errors.

    https://developers.google.com/actions/smarthome/create-app#error_responses
    """

    def __init__(self, code, msg):
        """Log error code."""
        super().__init__(msg)
        self.code = code


class Config:
    """Hold the configuration for Google Assistant."""

    def __init__(self, should_expose, allow_unlock,
                 entity_config=None):
        """Initialize the configuration."""
        self.should_expose = should_expose
        self.entity_config = entity_config or {}
        self.allow_unlock = allow_unlock


class RequestData:
    """Hold data associated with a particular request."""

    def __init__(self, config, user_id, request_id):
        """Initialize the request data."""
        self.config = config
        self.request_id = request_id
        self.context = Context(user_id=user_id)
