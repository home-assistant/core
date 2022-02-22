"""Representation of Plex buttons."""
from __future__ import annotations

import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_SERVER_IDENTIFIER, DOMAIN, PLEX_UPDATE_PLATFORMS_SIGNAL

CLIENT_SCAN_INTERVAL = datetime.timedelta(minutes=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Plex button from config entry."""
    server_id: str = config_entry.data[CONF_SERVER_IDENTIFIER]
    async_add_entities([PlexScanClientsButton(server_id)])


class PlexScanClientsButton(ButtonEntity):
    """Representation of a scan_clients button entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Scan Clients"

    def __init__(self, server_id: str) -> None:
        """Initialize a scan_clients Plex button entity."""
        self.server_id = server_id
        self._attr_unique_id = f"plex-scan_clients-{self.server_id}"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""

        async def async_scheduled_press(now: datetime.datetime):
            """Regularly press the button to automatically discover new clients."""
            await self.async_press()

        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                async_scheduled_press,
                CLIENT_SCAN_INTERVAL,
            )
        )

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
        )
