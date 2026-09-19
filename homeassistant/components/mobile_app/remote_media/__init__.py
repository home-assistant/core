"""Remote Now Playing: keep an iOS Now Playing card current without the app running.

The Home Assistant app can follow one `media_player`, and iOS 27 gives each followed session its
own APNs update token. This package stores those tokens, watches the players they belong to, and
pushes meaningful changes through the registration's existing push URL.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback

# Imported so the webhook command registrations in the submodule run on import.
from . import webhook  # noqa: F401
from .manager import async_get_manager
from .store import async_load_sessions, async_remove_registration

__all__ = [
    "async_registration_updated",
    "async_remove_entry",
    "async_remove_registration",
    "async_setup_entry",
    "async_unload_entry",
]


@callback
def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Resume this registration's Follow relationships.

    Per config entry rather than at integration startup, so a stored session is never mistaken for
    an orphan just because entries have not been set up yet.
    """
    sessions = async_load_sessions(hass, entry.data[CONF_WEBHOOK_ID])
    if not sessions:
        return
    async_get_manager(hass).async_restore(entry, sessions)


@callback
def async_registration_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Pick up relationships this registration can be pushed to now.

    `update_registration` is where an install that had no push configuration gains one. Nothing new
    is followed: only sessions already stored for this registration.
    """
    async_get_manager(hass).async_registration_updated(entry)


@callback
def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Detach this registration's listeners, keeping the relationships themselves.

    A reload or a shutdown is not the user stopping following, so nothing is removed and no `end`
    is sent.
    """
    async_get_manager(hass).async_unload_registration(entry.data[CONF_WEBHOOK_ID])


@callback
def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Forget this registration's Follow relationships for good.

    Telling the phone is best effort: a relay outage must not hold up deleting a config entry.
    """
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    manager = async_get_manager(hass)
    # The entry is passed in because Home Assistant unloads a config entry before removing one, so
    # it is no longer in `DATA_CONFIG_ENTRIES` to look its push configuration up in.
    manager.async_end_registration(entry)
    manager.async_unload_registration(webhook_id)
    async_remove_registration(hass, webhook_id)
