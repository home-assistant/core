"""Scoped auth tokens for sandbox runtimes (Phase 7).

Each sandbox group runs against a dedicated system user; the access token
the manager hands to the subprocess is issued from a refresh token whose
``scopes`` set restricts the websocket API to the ``sandbox_v2/``
namespace plus a short allow-list (e.g. ``auth/current_user``). The
websocket dispatcher enforces the scope per command — see
``homeassistant.components.websocket_api.connection._scope_allows``.

The sandbox does not currently open a websocket back to main, but the
scoped token is still issued and passed on the CLI so that:

* the manager and runtime agree on a real credential rather than a
  placeholder, and
* the opt-in subscription consumer designed in
  ``sandbox_v2/docs/design-share-states.md`` inherits the same scope
  without a separate code path.
"""

import logging

from homeassistant.auth.models import RefreshToken, User
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Websocket-API scopes granted to sandbox tokens.
#
# Entries ending in ``/`` are prefix grants — ``sandbox_v2/`` permits any
# ``sandbox_v2/...`` command. Plain entries are exact matches. Keep this
# allow-list minimal: every entry is a public API surface a sandboxed
# integration would otherwise be unable to call, so adding to it widens
# the trust boundary.
SANDBOX_TOKEN_SCOPES: frozenset[str] = frozenset(
    {
        "sandbox_v2/",
        # Lets the sandbox confirm which user it authenticated as.
        "auth/current_user",
    }
)

# Marker stored on the system user's name + refresh_token client_id so the
# manager can recognise (and reuse) an existing sandbox credential across
# HA restarts.
_USER_NAME_PREFIX = "Sandbox v2: "
_CLIENT_ID_PREFIX = "sandbox_v2/"


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
    """Issue a scoped access token for the sandbox runtime of ``group``.

    Reuses the dedicated system user across calls; rotates the refresh
    token on each call so a restart hands the subprocess a fresh
    credential. The returned JWT is the access token the runtime should
    pass on the websocket ``auth`` message.
    """
    user = await async_get_or_create_sandbox_user(hass, group)
    refresh_token = await _get_or_create_sandbox_refresh_token(hass, user, group)
    return hass.auth.async_create_access_token(refresh_token)


async def _get_or_create_sandbox_refresh_token(
    hass: HomeAssistant, user: User, group: str
) -> RefreshToken:
    """Return (or create) the sandbox refresh token for ``group``.

    Sandbox users are ``system_generated`` so their tokens are
    ``TOKEN_TYPE_SYSTEM`` and do not carry a ``client_id``. We identify
    a group's token by matching the ``scopes`` set against
    :data:`SANDBOX_TOKEN_SCOPES`; on first use, we create one.
    """
    for token in user.refresh_tokens.values():
        if token.scopes == SANDBOX_TOKEN_SCOPES:
            return token
    return await hass.auth.async_create_refresh_token(
        user,
        scopes=SANDBOX_TOKEN_SCOPES,
    )


__all__ = [
    "SANDBOX_TOKEN_SCOPES",
    "async_get_or_create_sandbox_user",
    "async_issue_sandbox_access_token",
]
