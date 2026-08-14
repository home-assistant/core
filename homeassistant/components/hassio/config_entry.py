"""Helpers for hassio config entry access."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    DEFAULT_UPDATE_OPTIONS,
    DOMAIN,
    OPTION_ADD_ON_BACKUP_BEFORE_UPDATE,
    OPTION_ADD_ON_BACKUP_RETAIN_COPIES,
    OPTION_CORE_BACKUP_BEFORE_UPDATE,
)


@callback
def async_get_hassio_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the active hassio config entry if it exists."""
    entries = hass.config_entries.async_entries(
        DOMAIN, include_ignore=False, include_disabled=False
    )
    return entries[0] if entries else None


@callback
def async_get_update_options(
    hass: HomeAssistant, entry: ConfigEntry | None = None
) -> dict[str, bool | int]:
    """Return hassio update options with defaults applied."""
    if entry is None:
        entry = async_get_hassio_entry(hass)

    if entry is None:
        return dict(DEFAULT_UPDATE_OPTIONS)

    return {
        OPTION_ADD_ON_BACKUP_BEFORE_UPDATE: entry.options.get(
            OPTION_ADD_ON_BACKUP_BEFORE_UPDATE,
            DEFAULT_UPDATE_OPTIONS[OPTION_ADD_ON_BACKUP_BEFORE_UPDATE],
        ),
        OPTION_ADD_ON_BACKUP_RETAIN_COPIES: entry.options.get(
            OPTION_ADD_ON_BACKUP_RETAIN_COPIES,
            DEFAULT_UPDATE_OPTIONS[OPTION_ADD_ON_BACKUP_RETAIN_COPIES],
        ),
        OPTION_CORE_BACKUP_BEFORE_UPDATE: entry.options.get(
            OPTION_CORE_BACKUP_BEFORE_UPDATE,
            DEFAULT_UPDATE_OPTIONS[OPTION_CORE_BACKUP_BEFORE_UPDATE],
        ),
    }
