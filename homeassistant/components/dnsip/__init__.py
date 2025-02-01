"""The dnsip component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import _LOGGER, HomeAssistant

from .const import CONF_PORT_IPV6, DEFAULT_PORT, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DNS IP from a config entry."""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload dnsip config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to a newer version."""

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version < 2 and config_entry.minor_version < 2:
        version = config_entry.version
        minor_version = config_entry.minor_version
        _LOGGER.debug(
            "Migrating configuration from version %s.%s",
            version,
            minor_version,
        )

        new_options = {**config_entry.options}
        new_options[CONF_PORT] = DEFAULT_PORT
        new_options[CONF_PORT_IPV6] = DEFAULT_PORT

        hass.config_entries.async_update_entry(
            config_entry, options=new_options, minor_version=2
        )

        _LOGGER.debug(
            "Migration to configuration version %s.%s successful",
            1,
            2,
        )

    return True
