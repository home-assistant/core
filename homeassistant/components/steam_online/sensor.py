"""Sensor for Steam account status."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    STEAM_API_URL,
    STEAM_HEADER_IMAGE_FILE,
    STEAM_ICON_URL,
    STEAM_MAIN_IMAGE_FILE,
    STEAM_STATUSES,
    SUBENTRY_TYPE_FRIEND,
)
from .coordinator import PlayerData, SteamConfigEntry, SteamDataUpdateCoordinator
from .entity import SteamEntity

PARALLEL_UPDATES = 1


class SteamSensor(StrEnum):
    """Steam sensors."""

    ACCOUNT = "account"


@dataclass(kw_only=True, frozen=True)
class SteamSensorEntityDescription(SensorEntityDescription):
    """Steam sensor description."""

    value_fn: Callable[[PlayerData], StateType]
    entity_picture_fn: Callable[[PlayerData], str] | None = None


SENSOR_DESCRIPTIONS: tuple[SteamSensorEntityDescription, ...] = (
    SteamSensorEntityDescription(
        key=SteamSensor.ACCOUNT,
        translation_key=SteamSensor.ACCOUNT,
        value_fn=lambda x: STEAM_STATUSES[x.personastate],
        entity_picture_fn=lambda x: x.avatarfull,
        name=None,
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
        SteamSensorEntity(coordinator, entry.unique_id, description)
        for description in SENSOR_DESCRIPTIONS
        if entry.unique_id is not None and entry.unique_id in coordinator.data
    )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_FRIEND):
        async_add_entities(
            [
                SteamSensorEntity(coordinator, subentry.unique_id, description)
                for description in SENSOR_DESCRIPTIONS
                if subentry.unique_id is not None
                and subentry.unique_id in coordinator.data
            ],
            config_subentry_id=subentry.subentry_id,
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
        if game := player.gameextrainfo:
            attrs["game"] = game
        if game_id := player.gameid:
            attrs["game_id"] = game_id
            game_url = f"{STEAM_API_URL}{player.gameid}/"
            attrs["game_image_header"] = f"{game_url}{STEAM_HEADER_IMAGE_FILE}"
            attrs["game_image_main"] = f"{game_url}{STEAM_MAIN_IMAGE_FILE}"
            if info := self._get_game_icon(player):
                attrs["game_icon"] = f"{STEAM_ICON_URL}{game_id}/{info}.jpg"
        if last_online := player.lastlogoff:
            attrs["last_online"] = dt_util.as_local(
                dt_util.utc_from_timestamp(last_online)
            )
        if level := self.coordinator.data[self._steamid].level:
            attrs["level"] = level
        return attrs

    def _get_game_icon(self, player: PlayerData) -> str | None:
        """Get game icon identifier."""
        if player.gameid is not None and player.gameid in self.coordinator.game_icons:
            return self.coordinator.game_icons[player.gameid]
        return None

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._steamid in self.coordinator.data
