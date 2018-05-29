"""Helper classes for Google Assistant integration."""


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

    def __init__(self, should_expose, agent_user_id, entity_config=None):
        """Initialize the configuration."""
        self.should_expose = should_expose
        self.agent_user_id = agent_user_id
        self.entity_config = entity_config or {}
