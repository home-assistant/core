"""The dlna_dmr component."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_PLATFORM, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER

PLATFORMS = [MEDIA_PLAYER_DOMAIN]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up DLNA component."""
    if MEDIA_PLAYER_DOMAIN not in config:
        return True

    for entry_config in config[MEDIA_PLAYER_DOMAIN]:
        if entry_config.get(CONF_PLATFORM) != DOMAIN:
            continue
        LOGGER.warning(
            "Configuring dlna_dmr via yaml is deprecated; the configuration for"
            " %s has been migrated to a config entry and can be safely removed",
            entry_config.get(CONF_URL),
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=entry_config,
            )
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up a DLNA DMR device from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    # Forward setup to the appropriate platform
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    # Forward to the same platform as async_setup_entry did
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
