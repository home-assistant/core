"""Helpers to interact with the backup integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.components.backup import BackupManager


DOMAIN = "backup"
DATA_MANAGER: HassKey[BackupManager] = HassKey(DOMAIN)


@callback
def async_get_manager(hass: HomeAssistant) -> BackupManager:
    """Get the backup manager instance.

    Raises HomeAssistantError if the backup integration is not available.
    """
    if DATA_MANAGER not in hass.data:
        raise HomeAssistantError("Backup integration is not available")

    return hass.data[DATA_MANAGER]
