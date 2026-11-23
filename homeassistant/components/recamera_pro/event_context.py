"""Home Assistant contexts shared by accepted event records."""

from homeassistant.core import Context


def new_event_context() -> Context:
    """Create one standards-compliant context for an accepted event."""
    return Context()
