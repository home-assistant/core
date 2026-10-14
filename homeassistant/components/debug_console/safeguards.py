"""Safeguards of the Debug console, on versions that are not for development.

Development and nightly versions are for people working on Home Assistant, so
these only apply to beta and stable versions: each user has to accept a warning
before using the console, and everything that runs is logged.
"""

import logging
from typing import Any

from homeassistant.auth import EVENT_USER_REMOVED
from homeassistant.auth.models import User
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    IS_DEVELOPMENT_VERSION,
    WARNING_VERSION,
)
from .inspection import class_name

_LOGGER = logging.getLogger(__name__)


@callback
def async_warning_required(hass: HomeAssistant, user_id: str) -> bool:
    """Return if a user still has to accept the warning before using the console."""
    if IS_DEVELOPMENT_VERSION:
        return False

    return not any(
        _warning_accepted(entry, user_id)
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    )


@callback
def async_accept_warning(hass: HomeAssistant, user_id: str) -> None:
    """Store that a user accepted the current version of the warning."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_WARNING_ACCEPTED: {
                    **entry.data.get(CONF_WARNING_ACCEPTED, {}),
                    user_id: {
                        "version": WARNING_VERSION,
                        "accepted_at": dt_util.utcnow().isoformat(),
                    },
                },
            },
        )


async def async_follow_removed_users(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Forget the acceptance of every user who is removed.

    Also of users removed while the debug console was not loaded.
    """
    users = {user.id for user in await hass.auth.async_get_users()}
    for user_id in list(entry.data.get(CONF_WARNING_ACCEPTED, {})):
        if user_id not in users:
            _async_forget_warning_acceptance(hass, entry, user_id)

    @callback
    def _async_forget_removed_user(event: Event) -> None:
        _async_forget_warning_acceptance(hass, entry, event.data["user_id"])

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_USER_REMOVED, _async_forget_removed_user)
    )


@callback
def async_log_execution(user: User, code: str) -> None:
    """Log code that runs, so a support request shows what was done."""
    if IS_DEVELOPMENT_VERSION:
        return

    _LOGGER.warning("%s ran code in the debug console:\n%s", user.name, code)


@callback
def async_log_property_evaluation(user: User, value: Any, attribute: str) -> None:
    """Log a property the user evaluated, as properties can change things too."""
    if IS_DEVELOPMENT_VERSION:
        return

    _LOGGER.warning(
        "%s evaluated %s.%s in the debug console",
        user.name,
        class_name(value),
        attribute,
    )


def _warning_accepted(entry: ConfigEntry, user_id: str) -> bool:
    """Return if a user accepted the current version of the warning."""
    acceptance = entry.data.get(CONF_WARNING_ACCEPTED, {}).get(user_id)
    return acceptance is not None and acceptance["version"] >= WARNING_VERSION


@callback
def _async_forget_warning_acceptance(
    hass: HomeAssistant, entry: ConfigEntry, user_id: str
) -> None:
    """Forget the acceptance of a user."""
    acceptances = entry.data.get(CONF_WARNING_ACCEPTED, {})
    if user_id not in acceptances:
        return

    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_WARNING_ACCEPTED: {
                accepted_by: acceptance
                for accepted_by, acceptance in acceptances.items()
                if accepted_by != user_id
            },
        },
    )
