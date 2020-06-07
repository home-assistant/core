"""Constants for climacell tests."""

from homeassistant.const import CONF_API_KEY


class MockRequestInfo:
    """Mock request info to use in ClientReponseError."""

    def __init__(self):
        """Initialize mock request info."""
        self.real_url = ""


API_KEY = "aa"

MIN_CONFIG = {
    CONF_API_KEY: API_KEY,
}
