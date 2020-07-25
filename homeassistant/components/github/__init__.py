"""The GitHub integration."""
import asyncio

from aiogithubapi import (
    AIOGitHubAPIAuthenticationException,
    AIOGitHubAPIException,
    GitHub,
)

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Config, HomeAssistant

from .const import DOMAIN

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up GitHub integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up GitHub from a config entry."""
    try:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = GitHub(
            entry.data[CONF_ACCESS_TOKEN]
        )
    except AIOGitHubAPIAuthenticationException as err:
        raise ConfigEntryNotReady from err
    except AIOGitHubAPIException as err:
        raise ConfigEntryNotReady from err

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
