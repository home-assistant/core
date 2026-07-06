"""HTTP specific constants."""

from typing import Final

from aiohttp.web import Request

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS  # noqa: F401

DOMAIN: Final = "http"

KEY_HASS_USER: Final = "hass_user"
KEY_HASS_REFRESH_TOKEN_ID: Final = "hass_refresh_token_id"
KEY_SUPERVISOR_UNIX_SOCKET: Final = "ha_supervisor_unix_socket"


def is_supervisor_unix_socket_request(request: Request) -> bool:
    """Check if request arrived over the Supervisor Unix socket.

    The result is cached on the request since it is checked by both the ban
    and auth middlewares.
    """
    cached: bool | None = request.get(KEY_SUPERVISOR_UNIX_SOCKET)
    if cached is not None:
        return cached
    # Cheapest check first: without a configured socket path this can never be
    # a Supervisor Unix socket request, so we avoid probing the transport.
    if (
        (http := request.app[KEY_HASS].http) is None
        or (supervisor_path := http.supervisor_unix_socket_path) is None
        or (transport := request.transport) is None
    ):
        result = False
    else:
        sockname: str | None = transport.get_extra_info("sockname")
        result = sockname == str(supervisor_path)
    request[KEY_SUPERVISOR_UNIX_SOCKET] = result
    return result
