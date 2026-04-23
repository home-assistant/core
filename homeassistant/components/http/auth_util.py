"""Auth utilities for the HTTP component."""

from __future__ import annotations

from ipaddress import ip_address

from aiohttp.web import Request

from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.http import current_request
from homeassistant.helpers.network import is_cloud_connection
from homeassistant.util.network import is_local


@callback
def async_user_not_allowed_do_auth(
    hass: HomeAssistant, user: User, request: Request | None = None
) -> str | None:
    """Validate that user is not allowed to do auth things.

    Returns a translation key from the http component exceptions if the user
    is not allowed to authenticate, or None if the user is allowed.
    """
    if not user.is_active:
        return "user_not_active"

    if not user.local_only:
        return None

    # User is marked as local only, check if they are allowed to do auth
    if request is None:
        request = current_request.get()

    if not request:
        return "no_request_available"

    if is_cloud_connection(hass):
        return "user_local_only"

    try:
        remote_address = ip_address(request.remote)  # type: ignore[arg-type]
    except ValueError:
        return "invalid_remote_ip"

    if is_local(remote_address):
        return None

    return "user_cannot_authenticate_remotely"


# Human-readable descriptions for auth access errors.
# Keys match the translation keys returned by async_user_not_allowed_do_auth.
AUTH_ACCESS_ERROR_DESCRIPTIONS: dict[str, str] = {
    "user_not_active": "User is not active",
    "no_request_available": "No request available to validate local access",
    "user_local_only": "User is local only",
    "invalid_remote_ip": "Invalid remote IP",
    "user_cannot_authenticate_remotely": "User cannot authenticate remotely",
}
