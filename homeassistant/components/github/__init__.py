"""The GitHub integration."""
import asyncio
import logging
from typing import Any, Dict

from aiogithubapi import (
    AIOGitHubAPIAuthenticationException,
    AIOGitHubAPIException,
    GitHub,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.entity import Entity

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


class GitHubEntity(Entity):
    """Defines a GitHub entity."""

    def __init__(
        self, github: GitHub, repository: str, unique_id: str, name: str, icon: str
    ) -> None:
        """Set up GitHub Entity."""
        self._github = github
        self._repository = repository
        self._unique_id = unique_id
        self._name = name
        self._icon = icon
        self._available = True

    @property
    def unique_id(self):
        """Return the unique_id of the sensor."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available


class GitHubDeviceEntity(GitHubEntity):
    """Defines a GitHub device entity."""

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this GitHub instance."""
        return {
            "identifiers": {(DOMAIN, self._repository)},
            "manufacturer": self._repository.split("/")[0],
            "name": self._repository,
        }
