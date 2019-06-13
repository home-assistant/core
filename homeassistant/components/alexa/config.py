"""Config helpers for Alexa."""


class Config:
    """Hold the configuration for Alexa."""

    def __init__(self, endpoint, async_get_access_token, should_expose,
                 entity_config=None):
        """Initialize the configuration."""
        self.endpoint = endpoint
        self.async_get_access_token = async_get_access_token
        self.should_expose = should_expose
        self.entity_config = entity_config or {}
