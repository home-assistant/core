"""Authentication helpers for the Anglian Water integration."""

from pyanglianwater.auth import MSOB2CAuth
from pyanglianwater.exceptions import ExpiredAccessTokenError, InvalidGrantError


async def async_force_login(auth: MSOB2CAuth) -> None:
    """Force a username/password login, bypassing refresh-token reuse."""
    refresh_token = auth.refresh_token
    next_refresh = auth.next_refresh
    auth._refresh_token = None  # noqa: SLF001
    auth.next_refresh = None
    try:
        await auth.send_login_request()
    except Exception:
        auth._refresh_token = refresh_token  # noqa: SLF001
        auth.next_refresh = next_refresh
        raise

    if auth.access_token is None:
        auth._refresh_token = refresh_token  # noqa: SLF001
        auth.next_refresh = next_refresh
        raise ExpiredAccessTokenError


async def async_refresh_or_force_login(auth: MSOB2CAuth) -> None:
    """Refresh the access token, falling back to a full login when needed."""
    try:
        await auth.send_refresh_request()
    except (ExpiredAccessTokenError, InvalidGrantError):
        await async_force_login(auth)
