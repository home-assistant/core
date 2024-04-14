"""Utils for pyLoad."""

from collections.abc import Mapping
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL


def api_url(user_input: dict[str, Any] | Mapping[str, Any]) -> str:
    """Build api url for PyLoadAPI."""
    proto = "https" if user_input.get(CONF_SSL, False) else "http"
    host = user_input.get(CONF_HOST, "localhost")
    port = user_input.get(CONF_PORT, 8000)
    return f"{proto}://{host}:{port}/"
