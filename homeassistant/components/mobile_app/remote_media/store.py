"""Persistence for Remote Now Playing sessions.

Uses the existing `mobile_app` store, the same way `live_activity` does, so a Follow relationship
survives a restart without the phone re-registering. Keyed by the webhook id of the config entry
that owns them, which is also how config-entry removal cleans them up.
"""

from functools import partial
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback

from ..const import (
    DATA_REMOTE_MEDIA_SESSIONS,
    DATA_STORE,
    DOMAIN,
    STORAGE_SAVE_DELAY_SECONDS,
)
from ..helpers import savable_state
from .model import RemoteMediaSession

_LOGGER = logging.getLogger(__name__)


@callback
def async_sessions_for(
    hass: HomeAssistant, webhook_id: str
) -> dict[str, dict[str, Any]]:
    """Return the stored sessions for one registration, keyed by session id."""
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS].get(webhook_id, {})


@callback
def async_load_sessions(
    hass: HomeAssistant, webhook_id: str
) -> list[RemoteMediaSession]:
    """Return the usable stored sessions for one registration.

    A stored entry that cannot be rebuilt is dropped rather than raised: the store is shared with
    the rest of `mobile_app`, and one malformed session must not stop a registration from loading.
    """
    sessions = []
    for session_id, data in async_sessions_for(hass, webhook_id).items():
        if (session := RemoteMediaSession.from_storage(data)) is None:
            _LOGGER.warning(
                "Discarding unreadable Remote Now Playing session %s", session_id
            )
            continue
        sessions.append(session)
    return sessions


@callback
def async_save_session(
    hass: HomeAssistant, webhook_id: str, session: RemoteMediaSession
) -> None:
    """Store or replace one session and schedule a save."""
    # pylint: disable-next=home-assistant-use-runtime-data
    domain_data = hass.data[DOMAIN]
    domain_data[DATA_REMOTE_MEDIA_SESSIONS].setdefault(webhook_id, {})[
        session.session_id
    ] = session.as_storage()
    domain_data[DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )


@callback
def async_remove_session(hass: HomeAssistant, webhook_id: str, session_id: str) -> bool:
    """Remove one session, returning whether it existed."""
    # pylint: disable-next=home-assistant-use-runtime-data
    domain_data = hass.data[DOMAIN]
    sessions = domain_data[DATA_REMOTE_MEDIA_SESSIONS]
    if (registration := sessions.get(webhook_id)) is None:
        return False
    if registration.pop(session_id, None) is None:
        return False
    if not registration:
        del sessions[webhook_id]
    domain_data[DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
    return True


@callback
def async_remove_registration(hass: HomeAssistant, webhook_id: str) -> None:
    """Forget every session belonging to one registration."""
    # pylint: disable-next=home-assistant-use-runtime-data
    domain_data = hass.data[DOMAIN]
    if domain_data[DATA_REMOTE_MEDIA_SESSIONS].pop(webhook_id, None) is None:
        return
    domain_data[DATA_STORE].async_delay_save(
        partial(savable_state, hass), STORAGE_SAVE_DELAY_SECONDS
    )
