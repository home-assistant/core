"""Config helpers for Alexa."""


class AbstractConfig:
    """Hold the configuration for Alexa."""

    @property
    def supports_auth(self):
        """Return if config supports auth."""
        return False

    @property
    def endpoint(self):
        """Endpoint for report state."""
        return None

    @property
    def entity_config(self):
        """Return entity config."""
        return {}

    def should_expose(self, entity_id):
        """If an entity should be exposed."""
        # pylint: disable=no-self-use
        return False

    async def async_get_access_token(self):
        """Get an access token."""
        raise NotImplementedError

    async def async_accept_grant(self, code):
        """Accept a grant."""
        raise NotImplementedError
