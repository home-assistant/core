"""WebSocket API related errors."""
from homeassistant.exceptions import HomeAssistantError


class Disconnect(HomeAssistantError):
    """Disconnect the current session."""
