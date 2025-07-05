"""Representation of Plex updates."""

import logging
from typing import Any

from plexapi.exceptions import PlexApiException
import requests.exceptions

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SERVER_IDENTIFIER, DOMAIN
from .helpers import get_plex_server

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Plex update entities from a config entry."""
    server_id = config_entry.data[CONF_SERVER_IDENTIFIER]
    server = get_plex_server(hass, server_id)
    can_update = await hass.async_add_executor_job(server.plex_server.canInstallUpdate)
    async_add_entities([PlexUpdate(server, can_update)], update_before_add=True)


class PlexUpdate(UpdateEntity):
    """Representation of a Plex server update entity."""

    _attr_supported_features = UpdateEntityFeature.RELEASE_NOTES
    _release_notes: str | None = None
    _attr_translation_key: str = "server_update"
    _attr_has_entity_name = True

    def __init__(self, plex_server, can_update: bool) -> None:
        """Initialize the Update entity."""
        self._server = plex_server
        self._attr_unique_id = plex_server.machine_identifier
        if can_update:
            self._attr_supported_features |= UpdateEntityFeature.INSTALL

    def update(self) -> None:
        """Update sync attributes."""
        self._attr_installed_version = self._server.version
        try:
            if (release := self._server.plex_server.checkForUpdate()) is None:
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
            self._server.plex_server.installUpdate()
        except (requests.exceptions.RequestException, PlexApiException) as exc:
            raise HomeAssistantError(str(exc)) from exc

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._server.machine_identifier)},
            manufacturer="Plex",
            model="Plex Media Server",
            name=self._server.friendly_name,
            sw_version=self._server.version,
            configuration_url=f"{self._server.url_in_use}/web",
        )
