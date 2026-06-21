"""Sensor for Steam account status."""

from datetime import datetime
from typing import cast, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCOUNTS,
    STEAM_API_URL,
    STEAM_HEADER_IMAGE_FILE,
    STEAM_ICON_URL,
    STEAM_MAIN_IMAGE_FILE,
    STEAM_STATUSES,
)
from .coordinator import SteamConfigEntry, SteamDataUpdateCoordinator
from .entity import SteamEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Steam platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        SteamSensor(coordinator, steamid)
        for steamid in entry.options[CONF_ACCOUNTS]
        if steamid in coordinator.data
    )


class SteamSensor(SteamEntity, SensorEntity):
    """A class for the Steam account."""

    _attr_translation_key = "account"
    _attr_has_entity_name = True

    def __init__(self, coordinator: SteamDataUpdateCoordinator, steamid: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._steamid = steamid
        self._attr_unique_id = f"sensor.steam_{steamid}"
        self._attr_name = str(coordinator.data[steamid]["personaname"])
        self._attr_entity_picture = str(coordinator.data[steamid]["avatarmedium"])

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return STEAM_STATUSES[
            cast(int, self.coordinator.data[self._steamid]["personastate"])
        ]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | int | datetime]:
        """Return the state attributes of the sensor."""
        player = self.coordinator.data[self._steamid]

        attrs: dict[str, str | int | datetime] = {}
        if game := player.get("gameextrainfo"):
            attrs["game"] = game
        if game_id := player.get("gameid"):
            attrs["game_id"] = game_id
            game_url = f"{STEAM_API_URL}{player['gameid']}/"
            attrs["game_image_header"] = f"{game_url}{STEAM_HEADER_IMAGE_FILE}"
            attrs["game_image_main"] = f"{game_url}{STEAM_MAIN_IMAGE_FILE}"
            if info := self._get_game_icon(player):
                attrs["game_icon"] = f"{STEAM_ICON_URL}{game_id}/{info}.jpg"
        if last_online := cast(int | None, player.get("lastlogoff")):
            attrs["last_online"] = dt_util.as_local(
                dt_util.utc_from_timestamp(last_online)
            )
        if level := self.coordinator.data[self._steamid]["level"]:
            attrs["level"] = level
        return attrs

    def _get_game_icon(self, player: dict) -> str | None:
        """Get game icon identifier."""
        if player.get("gameid") in self.coordinator.game_icons:
            return self.coordinator.game_icons[player["gameid"]]
        # Reset game icons to have coordinator get id for new game
        self.coordinator.game_icons = {}
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return super().available and self._steamid in self.coordinator.data
