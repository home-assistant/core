"""Safeguards of the Debug console.

Each user has to accept a warning before using the console, and everything that
runs is logged, with who ran it.
"""

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.auth import EVENT_USER_REMOVED
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import CONF_WARNING_ACCEPTED, DOMAIN, WARNING_VERSION
from .inspection import class_name

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


@dataclass(slots=True)
class WarningAcceptances:
    """The users who accepted the warning, and which version of it."""

    store: Store[dict[str, Any]]
    accepted: dict[str, dict[str, Any]]

    async def async_save(self) -> None:
        """Store the acceptances."""
        await self.store.async_save({CONF_WARNING_ACCEPTED: self.accepted})


DATA_WARNING_ACCEPTANCES: HassKey[WarningAcceptances] = HassKey(
    f"{DOMAIN}_{CONF_WARNING_ACCEPTED}"
)


async def async_setup_safeguards(hass: HomeAssistant) -> None:
    """Load who accepted the warning, and forget users once they are removed.

    Also users removed while the debug console was not loaded.
    """
    store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load() or {}
    acceptances = hass.data[DATA_WARNING_ACCEPTANCES] = WarningAcceptances(
        store, data.get(CONF_WARNING_ACCEPTED, {})
    )

    users = {user.id for user in await hass.auth.async_get_users()}
    if removed := set(acceptances.accepted) - users:
        for user_id in removed:
            del acceptances.accepted[user_id]

        await acceptances.async_save()

    async def _async_forget_removed_user(event: Event) -> None:
        if acceptances.accepted.pop(event.data["user_id"], None) is not None:
            await acceptances.async_save()

    hass.bus.async_listen(EVENT_USER_REMOVED, _async_forget_removed_user)


@callback
def async_warning_required(hass: HomeAssistant, user_id: str) -> bool:
    """Return if a user still has to accept the warning before using the console."""
    acceptance = hass.data[DATA_WARNING_ACCEPTANCES].accepted.get(user_id)
    return acceptance is None or acceptance["version"] < WARNING_VERSION


async def async_accept_warning(hass: HomeAssistant, user_id: str) -> None:
    """Store that a user accepted the current version of the warning."""
    acceptances = hass.data[DATA_WARNING_ACCEPTANCES]
    acceptances.accepted[user_id] = {
        "version": WARNING_VERSION,
        "accepted_at": dt_util.utcnow().isoformat(),
    }
    await acceptances.async_save()


@callback
def async_log_execution(connection: ActiveConnection, code: str) -> None:
    """Log code that runs, so a support request shows what was done."""
    _LOGGER.warning(
        "%s ran code in the debug console:\n%s", _describe_user(connection), code
    )


@callback
def async_log_inspection(connection: ActiveConnection, value: Any) -> None:
    """Log an object the user expanded, as reading its items runs its code."""
    _LOGGER.warning(
        "%s expanded a %s in the debug console",
        _describe_user(connection),
        class_name(value),
    )


@callback
def async_log_property_evaluation(
    connection: ActiveConnection, value: Any, attribute: str
) -> None:
    """Log a property the user evaluated, as properties can change things too."""
    _LOGGER.warning(
        "%s evaluated %s.%s in the debug console",
        _describe_user(connection),
        class_name(value),
        attribute,
    )


def _describe_user(connection: ActiveConnection) -> str:
    """Describe who uses the console, down to the login and where from.

    A name alone does not tell apart the sessions of a user, like one that is
    not theirs.
    """
    return (
        f"{connection.user.name} (user {connection.user.id}, "
        f"refresh token {connection.refresh_token_id}, from {connection.remote})"
    )
