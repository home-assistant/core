"""Representation of Plex updates."""
import logging
from typing import Any

from plexapi.exceptions import PlexApiException
import plexapi.server
import requests.exceptions

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Set up Plex media_player from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    server = get_plex_server(hass, server_id)
    plex_server = server.plex_server
    async_add_entities([PlexUpdate(plex_server)], update_before_add=True)


class PlexUpdate(UpdateEntity):
    """Representation of a Plex server update entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(self, plex_server: plexapi.server.PlexServer) -> None:
        """Initialize the Update entity."""
        self.plex_server = plex_server
        self.can_update: bool = False
        self._attr_name = f"Plex Media Server ({plex_server.friendlyName})"
        self._attr_unique_id = plex_server.machineIdentifier
        self._release_notes: str | None = None

    def update(self) -> None:
        """Update sync attributes."""
        self._attr_installed_version = self.plex_server.version
        try:
            if (release := self.plex_server.checkForUpdate()) is None:
                return
            self.can_update = self.plex_server.canInstallUpdate()
        except (requests.exceptions.RequestException, PlexApiException):
            _LOGGER.warning("Polling update sensor failed, will try again")
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
        if not self.can_update:
            raise HomeAssistantError(
                "Automatic updates cannot be performed on this Plex installation"
            )
        try:
            self.plex_server.installUpdate()
        except (requests.exceptions.RequestException, PlexApiException) as exc:
            raise HomeAssistantError(str(exc)) from exc
