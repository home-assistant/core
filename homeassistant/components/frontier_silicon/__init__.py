"""The Frontier Silicon integration."""
from __future__ import annotations

import logging

from afsapi import AFSAPI, ConnectionError as FSConnectionError, InvalidPinException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, PlatformNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import CONF_PIN, CONF_WEBFSAPI_URL, DEFAULT_PIN, DEFAULT_PORT, DOMAIN

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Perform migration from YAML config to Config Flow entity."""

    async def _migrate_entry(entry_to_migrate):

        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_NAME: entry_to_migrate.get(CONF_NAME),
                CONF_HOST: entry_to_migrate.get(CONF_HOST),
                CONF_PORT: entry_to_migrate.get(CONF_PORT, DEFAULT_PORT),
                CONF_PIN: entry_to_migrate.get(CONF_PASSWORD, DEFAULT_PIN),
            },
        )

        ir.async_create_issue(
            hass,
            DOMAIN,
            "remove_yaml",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="removed_yaml",
        )

    for entry_to_migrate in config.get(Platform.MEDIA_PLAYER, []):
        if entry_to_migrate.get(CONF_PLATFORM) == DOMAIN:
            hass.async_create_task(_migrate_entry(entry_to_migrate))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Frontier Silicon from a config entry."""

    webfsapi_url = entry.data[CONF_WEBFSAPI_URL]
    pin = entry.data[CONF_PIN]

    afsapi = AFSAPI(webfsapi_url, pin)

    try:
        await afsapi.get_power()
    except FSConnectionError as exception:
        raise PlatformNotReady from exception
    except InvalidPinException as exception:
        raise ConfigEntryAuthFailed(exception) from exception

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = afsapi

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
