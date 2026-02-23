"""HTTP specific constants."""

import socket
from typing import Final

from aiohttp.web import Request

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS  # noqa: F401

DOMAIN: Final = "http"

KEY_HASS_USER: Final = "hass_user"
KEY_HASS_REFRESH_TOKEN_ID: Final = "hass_refresh_token_id"


def is_unix_socket_request(request: Request) -> bool:
    """Check if request arrived over a Unix socket."""
    if (transport := request.transport) is None:
        return False
    if (sock := transport.get_extra_info("socket")) is None:
        return False
    return bool(sock.family == socket.AF_UNIX)
