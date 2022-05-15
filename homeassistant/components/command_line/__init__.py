"""The command_line component."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Command Line component to import config."""

    if Platform.NOTIFY not in config:
        return True

    entry: dict[str, Any]
    for entry in config[Platform.NOTIFY]:
        if entry[CONF_PLATFORM] == DOMAIN:
            _LOGGER.warning(
                # Command Line config flow added in 2022.6 and should be removed in 2022.8
                "Configuration of the Command Line Notify platform in YAML is deprecated and "
                "will be removed in Home Assistant 2022.8; Your existing configuration "
                "has been imported into the UI automatically and can be safely removed "
                "from your configuration.yaml file"
            )
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={**entry, CONF_PLATFORM: "notify"},
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up command line from a config entry."""

    platform = [entry.options[CONF_PLATFORM]]

    if platform == [Platform.NOTIFY]:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.options
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                hass.data[DOMAIN][entry.entry_id],
                hass.data[DOMAIN],
            )
        )
        return True

    hass.config_entries.async_setup_platforms(entry, platform)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload command line config entry."""

    platform = [entry.options[CONF_PLATFORM]]
    return await hass.config_entries.async_unload_platforms(entry, platform)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    await hass.config_entries.async_reload(entry.entry_id)
