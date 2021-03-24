"""Support for automation and script tracing and debugging."""
from . import websocket_api
from .const import DATA_TRACE

DOMAIN = "trace"


async def async_setup(hass, config):
    """Initialize the trace integration."""
    hass.data.setdefault(DATA_TRACE, {})
    websocket_api.async_setup(hass)
    return True
