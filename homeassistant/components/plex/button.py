"""Representation of Plex buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex button from config entry."""
    server_id: str = config_entry.data[CONF_SERVER_IDENTIFIER]
    server_name: str = config_entry.data[CONF_SERVER]
    async_add_entities([PlexScanClientsButton(server_id, server_name)])


class PlexScanClientsButton(ButtonEntity):
    """Representation of a scan_clients button entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "scan_clients"

    def __init__(self, server_id: str, server_name: str) -> None:
        """Initialize a scan_clients Plex button entity."""
        self.server_id = server_id
        self._server_name = server_name
        self._attr_unique_id = f"plex-scan_clients-{self.server_id}"

    async def async_press(self) -> None:
        """Press the button."""
        async_dispatcher_send(
            self.hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(self.server_id)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.server_id)},
            manufacturer="Plex",
            name=self._server_name,
        )
