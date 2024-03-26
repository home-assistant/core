"""Representation of Plex updates."""

import logging
from typing import Any

from plexapi.exceptions import PlexApiException
import plexapi.server
import requests.exceptions

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SERVER_IDENTIFIER
from .helpers import get_plex_server

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex update entities from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    server = get_plex_server(hass, server_id)
    plex_server = server.plex_server
    can_update = await hass.async_add_executor_job(plex_server.canInstallUpdate)
    async_add_entities([PlexUpdate(plex_server, can_update)], update_before_add=True)


class PlexUpdate(UpdateEntity):
    """Representation of a Plex server update entity."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _release_notes: str | None = None

    def __init__(
        self, plex_server: plexapi.server.PlexServer, can_update: bool
    ) -> None:
        """Initialize the Update entity."""
        self.plex_server = plex_server
        self._attr_name = f"Plex Media Server ({plex_server.friendlyName})"
        self._attr_unique_id = plex_server.machineIdentifier
        if can_update:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

    def update(self) -> None:
        """Update sync attributes."""
        self._attr_installed_version = self.plex_server.version
        try:
            if (release := self.plex_server.checkForUpdate()) is None:
                self._attr_latest_version = self.installed_version
                return
        except (requests.exceptions.RequestException, PlexApiException):
            _LOGGER.debug("Polling update sensor failed, will try again")
            return
        self._attr_latest_version = release.version
        if release.fixed:
            self._release_notes = "\n".join(
                f"* {line}" for line in release.fixed.split("\n")
            )
        else:
            self._release_notes = None

    def release_notes(self) -> str | None:
        """Return release notes for the available upgrade."""
        return self._release_notes

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        try:
            self.plex_server.installUpdate()
        except (requests.exceptions.RequestException, PlexApiException) as exc:
            raise HomeAssistantError(str(exc)) from exc
