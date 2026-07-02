"""HTTP specific constants."""

from typing import Final

from aiohttp.web import Request

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS  # noqa: F401

DOMAIN: Final = "http"

KEY_HASS_USER: Final = "hass_user"
KEY_HASS_REFRESH_TOKEN_ID: Final = "hass_refresh_token_id"


def is_supervisor_unix_socket_request(request: Request) -> bool:
    """Check if request arrived over the Supervisor Unix socket."""
    if (transport := request.transport) is None:
        return False
    if (http := request.app[KEY_HASS].http) is None or (
        supervisor_path := http.supervisor_unix_socket_path
    ) is None:
        return False
    sockname: str | None = transport.get_extra_info("sockname")
    return sockname == str(supervisor_path)
