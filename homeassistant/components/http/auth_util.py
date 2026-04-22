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
    """Validate that user is not allowed to do auth things."""
    if not user.is_active:
        return "User is not active"

    if not user.local_only:
        return None

    # User is marked as local only, check if they are allowed to do auth
    if request is None:
        request = current_request.get()

    if not request:
        return "No request available to validate local access"

    if is_cloud_connection(hass):
        return "User is local only"

    try:
        remote_address = ip_address(request.remote)  # type: ignore[arg-type]
    except ValueError:
        return "Invalid remote IP"

    if is_local(remote_address):
        return None

    return "User cannot authenticate remotely"
