"""Sensor for Steam account status."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, cast, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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


class SteamSensor(StrEnum):
    """Steam sensors."""

    ACCOUNT = "account"


@dataclass(kw_only=True, frozen=True)
class SteamSensorEntityDescription(SensorEntityDescription):
    """Steam sensor description."""

    value_fn: Callable[[dict[str, Any]], StateType]
    name_fn: Callable[[dict[str, Any]], str]
    entity_picture_fn: Callable[[dict[str, Any]], str] | None = None


SENSOR_DESCRIPTIONS: tuple[SteamSensorEntityDescription, ...] = (
    SteamSensorEntityDescription(
        key=SteamSensor.ACCOUNT,
        translation_key=SteamSensor.ACCOUNT,
        value_fn=lambda x: STEAM_STATUSES[x["personastate"]],
        name_fn=lambda x: x["personaname"],
        entity_picture_fn=lambda x: x["avatarfull"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Steam platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        SteamSensorEntity(coordinator, steamid, description)
        for steamid in entry.options[CONF_ACCOUNTS]
        for description in SENSOR_DESCRIPTIONS
        if steamid in coordinator.data
    )


class SteamSensorEntity(SteamEntity, SensorEntity):
    """Representation of a Steam sensor entity."""

    entity_description: SteamSensorEntityDescription

    def __init__(
        self,
        coordinator: SteamDataUpdateCoordinator,
        steamid: str,
        description: SteamSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, steamid, description)
        self._attr_name = self.entity_description.name_fn(coordinator.data[steamid])

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._steamid])

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        return (
            fn(self.coordinator.data[self._steamid])
            if (fn := self.entity_description.entity_picture_fn) is not None
            else super().entity_picture
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
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
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._steamid in self.coordinator.data
