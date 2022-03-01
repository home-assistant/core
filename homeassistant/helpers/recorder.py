"""Helpers to check recorder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from homeassistant.components.recorder import Recorder


def has_recorder(hass: HomeAssistant) -> bool:
    """Return true if recorder is loaded."""
    return "recorder" in hass.config.components


def async_migration_in_progress(hass: HomeAssistant) -> bool:
    """Check to see if a recorder migration is in progress."""
    if not has_recorder(hass):
        return False
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    return recorder.util.async_migration_in_progress(hass)


async def lock_database(hass: HomeAssistant) -> bool:
    """
    Lock the database.

    raises TimeoutError if takes too long to lock the database.
    """
    instance: Recorder = hass.data["recorder_instance"]
    return await instance.lock_database()


@callback
def unlock_database(hass: HomeAssistant) -> bool:
    """Unlock the database."""
    instance: Recorder = hass.data["recorder_instance"]
    return instance.unlock_database()
