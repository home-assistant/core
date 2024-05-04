"""Representation of Plex buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlexServer
from .const import CONF_SERVER_IDENTIFIER, DOMAIN, PLEX_UPDATE_PLATFORMS_SIGNAL
from .helpers import get_plex_server


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex button from config entry."""
    server_id: str = config_entry.data[CONF_SERVER_IDENTIFIER]
    plex_server = get_plex_server(hass, server_id)
    async_add_entities([PlexScanClientsButton(server_id, plex_server)])


class PlexScanClientsButton(ButtonEntity):
    """Representation of a scan_clients button entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "scan_clients"

    def __init__(self, server_id: str, plex_server: PlexServer) -> None:
        """Initialize a scan_clients Plex button entity."""
        self.server_id = server_id
        self._attr_unique_id = f"plex-scan_clients-{self.server_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, server_id)},
            name=plex_server.friendly_name,
            manufacturer="Plex",
        )

    async def async_press(self) -> None:
        """Press the button."""
        async_dispatcher_send(
            self.hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(self.server_id)
        )
