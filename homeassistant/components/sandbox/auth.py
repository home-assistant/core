"""Auth tokens for sandbox runtimes.

Each sandbox group runs against a dedicated system user; the access token
the manager hands to the subprocess is issued from that user's refresh
token. The token is a plain system-user credential — there is no scope
restriction. The sandbox does not currently open a websocket back to main,
so no enforcement surface exists; scope enforcement is deferred until the
sandbox→main connection actually lands (see
``sandbox/docs/auth-scoping-decision.md``, kept as a historical design
record for that future work).
"""

import logging

from homeassistant.auth.models import RefreshToken, User
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Marker stored on the system user's name + refresh_token client_id so the
# manager can recognise (and reuse) an existing sandbox credential across
# HA restarts.
_USER_NAME_PREFIX = "Sandbox: "
_CLIENT_ID_PREFIX = "sandbox/"


def _user_name_for_group(group: str) -> str:
    """System user name for a given sandbox group."""
    return f"{_USER_NAME_PREFIX}{group}"


def _client_id_for_group(group: str) -> str:
    """Stable client_id for a sandbox group's refresh token."""
    return f"{_CLIENT_ID_PREFIX}{group}"


async def async_get_or_create_sandbox_user(hass: HomeAssistant, group: str) -> User:
    """Return the dedicated system user for ``group``, creating it once."""
    name = _user_name_for_group(group)
    for user in await hass.auth.async_get_users():
        if user.system_generated and user.name == name:
            return user
    return await hass.auth.async_create_system_user(name)


async def async_issue_sandbox_access_token(hass: HomeAssistant, group: str) -> str:
    """Issue an access token for the sandbox runtime of ``group``.

    Reuses the dedicated system user and its refresh token across calls;
    the access token is freshly minted each call so a restart hands the
    subprocess a fresh credential. The returned JWT is the access token
    the runtime should pass on the websocket ``auth`` message.
    """
    user = await async_get_or_create_sandbox_user(hass, group)
    refresh_token = await _get_or_create_sandbox_refresh_token(hass, user)
    return hass.auth.async_create_access_token(refresh_token)


async def _get_or_create_sandbox_refresh_token(
    hass: HomeAssistant, user: User
) -> RefreshToken:
    """Return (or create) the sandbox refresh token for ``user``.

    Sandbox users are ``system_generated`` and only ever get a single
    refresh token, so we identify it by that one-token-per-user invariant:
    reuse the existing token if present, otherwise create one.
    """
    tokens = list(user.refresh_tokens.values())
    if tokens:
        return tokens[0]
    return await hass.auth.async_create_refresh_token(user)


__all__ = [
    "async_get_or_create_sandbox_user",
    "async_issue_sandbox_access_token",
]
