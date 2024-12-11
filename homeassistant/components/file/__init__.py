"""The file component."""

from copy import deepcopy
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, CONF_NAME, CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a file component entry."""
    config = {**entry.data, **entry.options}
    filepath: str = config[CONF_FILE_PATH]
    if filepath and not await hass.async_add_executor_job(
        hass.config.is_allowed_path, filepath
    ):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="dir_not_allowed",
            translation_placeholders={"filename": filepath},
        )

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(entry.data[CONF_PLATFORM])]
    )
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [entry.data[CONF_PLATFORM]]
    )


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate config entry."""
    if config_entry.version > 2:
        # Downgraded from future
        return False

    if config_entry.version < 2:
        # Move optional fields from data to options in config entry
        data: dict[str, Any] = deepcopy(dict(config_entry.data))
        options = {}
        for key, value in config_entry.data.items():
            if key not in (CONF_FILE_PATH, CONF_PLATFORM, CONF_NAME):
                data.pop(key)
                options[key] = value

        hass.config_entries.async_update_entry(
            config_entry, version=2, data=data, options=options
        )
    return True
