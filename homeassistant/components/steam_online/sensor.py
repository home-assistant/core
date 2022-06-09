"""Sensor for Steam account status."""
from __future__ import annotations

from datetime import datetime
from time import localtime, mktime

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.util.dt import utc_from_timestamp

from . import SteamEntity
from .const import (
    CONF_ACCOUNTS,
    DOMAIN,
    STEAM_API_URL,
    STEAM_HEADER_IMAGE_FILE,
    STEAM_ICON_URL,
    STEAM_MAIN_IMAGE_FILE,
    STEAM_STATUSES,
)
from .coordinator import SteamDataUpdateCoordinator

# Deprecated in Home Assistant 2022.5
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_ACCOUNTS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)

PARALLEL_UPDATES = 1


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Twitch sensor from yaml."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Steam platform."""
    async_add_entities(
        SteamSensor(hass.data[DOMAIN][entry.entry_id], account)
        for account in entry.options[CONF_ACCOUNTS]
    )


class SteamSensor(SteamEntity, SensorEntity):
    """A class for the Steam account."""

    def __init__(self, coordinator: SteamDataUpdateCoordinator, account: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = SensorEntityDescription(
            key=account,
            name=f"steam_{account}",
            icon="mdi:steam",
        )
        self._attr_unique_id = f"sensor.steam_{account}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.key in self.coordinator.data:
            player = self.coordinator.data[self.entity_description.key]
            return STEAM_STATUSES[player["personastate"]]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str | datetime]:
        """Return the state attributes of the sensor."""
        if self.entity_description.key not in self.coordinator.data:
            return {}
        player = self.coordinator.data[self.entity_description.key]

        attrs: dict[str, str | datetime] = {}
        if game := player.get("gameextrainfo"):
            attrs["game"] = game
        if game_id := player.get("gameid"):
            attrs["game_id"] = game_id
            game_url = f"{STEAM_API_URL}{player['gameid']}/"
            attrs["game_image_header"] = f"{game_url}{STEAM_HEADER_IMAGE_FILE}"
            attrs["game_image_main"] = f"{game_url}{STEAM_MAIN_IMAGE_FILE}"
            if info := self._get_game_icon(player):
                attrs["game_icon"] = f"{STEAM_ICON_URL}{game_id}/{info}.jpg"
        self._attr_name = player["personaname"]
        self._attr_entity_picture = player["avatarmedium"]
        if last_online := player.get("lastlogoff"):
            attrs["last_online"] = utc_from_timestamp(mktime(localtime(last_online)))
        if level := self.coordinator.data[self.entity_description.key]["level"]:
            attrs["level"] = level
        return attrs

    def _get_game_icon(self, player: dict) -> str | None:
        """Get game icon identifier."""
        if player.get("gameid") in self.coordinator.game_icons:
            return self.coordinator.game_icons[player["gameid"]]
        # Reset game icons to have coordinator get id for new game
        self.coordinator.game_icons = {}
        return None
