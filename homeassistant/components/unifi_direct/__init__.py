"""The UniFi AP Direct integration."""

import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import DEFAULT_SSH_PORT
from .coordinator import UniFiDirectConfigEntry, UniFiDirectDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: UniFiDirectConfigEntry
) -> bool:
    """Migrate config entries to the multi-host format."""
    if config_entry.version < 2:
        host_configs: list[dict[str, object]] = []
        host = config_entry.data.get(CONF_HOST)
        if host is not None:
            host_configs.append(
                {
                    CONF_HOST: host,
                    CONF_USERNAME: config_entry.data.get(CONF_USERNAME, ""),
                    CONF_PASSWORD: config_entry.data.get(CONF_PASSWORD, ""),
                    CONF_PORT: config_entry.data.get(CONF_PORT, DEFAULT_SSH_PORT),
                }
            )

        if host_configs:
            hass.config_entries.async_update_entry(
                config_entry, data={CONF_HOSTS: host_configs}, version=2
            )

        _LOGGER.debug(
            "Migrated UniFi Direct config entry %s to version 2",
            config_entry.entry_id,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: UniFiDirectConfigEntry) -> bool:
    """Set up UniFi Direct from a config entry."""
    coordinator = UniFiDirectDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UniFiDirectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
