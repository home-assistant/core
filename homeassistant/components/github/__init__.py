"""The GitHub integration."""
import asyncio
import logging

from aiogithubapi import (
    AIOGitHubAPIAuthenticationException,
    AIOGitHubAPIException,
    GitHub,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Config, HomeAssistant

from .const import CONF_REPOSITORY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up GitHub integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up GitHub from a config entry."""
    try:
        github = GitHub(entry.data[CONF_ACCESS_TOKEN])
        await github.get_repo(entry.data[CONF_REPOSITORY])
    except (AIOGitHubAPIAuthenticationException, AIOGitHubAPIException):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "reauth"}, data=entry.data
            )
        )
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = github

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
