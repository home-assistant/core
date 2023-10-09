"""Representation of Plex updates."""
import logging
from typing import Any

import plexapi.server

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

    def _fetch_data() -> tuple[bool, str, plexapi.server.Release | None]:
        """Fetch all data from the Plex server in a single method."""
        return (
            plex_server.canInstallUpdate(),
            plex_server.version,
            plex_server.checkForUpdate(),
        )

    can_update, current_version, available_release = await hass.async_add_executor_job(
        _fetch_data
    )
    _LOGGER.debug("Creating Plex updater")

    available_version: str | None = None
    release_notes: str | None = None
    if available_release:
        available_version = available_release.version
        release_notes = available_release.fixed

    plex_update = PlexUpdate(
        plex_server, can_update, current_version, available_version, release_notes
    )
    async_add_entities([plex_update])


class PlexUpdate(UpdateEntity):
    """Representation of a Plex server update entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(
        self,
        plex_server: plexapi.server.PlexServer,
        can_update: bool,
        current_version: str,
        available_version: str | None,
        release_notes: str | None,
    ) -> None:
        """Initialize the Update entity."""
        self.plex_server = plex_server
        self.can_update = can_update
        self._attr_name = f"Plex Media Server ({plex_server.friendlyName})"
        self._attr_latest_version = available_version
        self._attr_installed_version = current_version
        self._attr_unique_id = plex_server.machineIdentifier
        self._release_notes = release_notes

    def update(self) -> None:
        """Update sync attributes."""
        self._attr_installed_version = self.plex_server.version
        if release := self.plex_server.checkForUpdate():
            self._attr_latest_version = release.version
            self._release_notes = release.fixed

    def release_notes(self) -> str | None:
        """Return release notes for the available upgrade."""
        if not self._release_notes:
            return None
        return "\n".join(f"* {line}" for line in self._release_notes.split("\n"))

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update."""
        if not self.plex_server.canInstallUpdate():
            raise HomeAssistantError(
                "Automatic updates cannot be performed on this Plex installation"
            )
        self.plex_server.installUpdate()
