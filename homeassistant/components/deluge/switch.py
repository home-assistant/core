"""Support for setting the Deluge BitTorrent client in Pause."""
from __future__ import annotations

from typing import Any

from deluge_client import DelugeRPCClient
import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DelugeEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DEFAULT_RPC_PORT, DOMAIN

# Deprecated in Home Assistant 2021.12
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_RPC_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_NAME, default="Deluge Switch"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Deluge sensor component."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Deluge switch."""
    async_add_entities(
        [
            DelugeSwitch(
                hass.data[DOMAIN][entry.entry_id][DATA_KEY_API],
                hass.data[DOMAIN][entry.entry_id][DATA_KEY_COORDINATOR],
                entry.title,
                entry.entry_id,
            )
        ]
    )


class DelugeSwitch(DelugeEntity, ToggleEntity):
    """Representation of a Deluge switch."""

    def __init__(
        self,
        api: DelugeRPCClient,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize the Deluge switch."""
        super().__init__(api, coordinator, server_unique_id)
        self._attr_name = name
        self._attr_unique_id = f"{server_unique_id}/Deluge Switch"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        torrent_ids = self.api.call("core.get_session_state")
        self.api.call("core.resume_torrent", torrent_ids)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        torrent_ids = self.api.call("core.get_session_state")
        self.api.call("core.pause_torrent", torrent_ids)

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        if self.coordinator.data:
            data: dict = self.coordinator.data[SWITCH_DOMAIN]
            for torrent in data.values():
                item = torrent.popitem()
                if not item[1]:
                    return True
        return False
