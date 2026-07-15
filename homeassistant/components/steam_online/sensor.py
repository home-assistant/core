"""Sensor for Steam account status."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from .coordinator import PlayerData, SteamConfigEntry
from .entity import SteamEntity

PARALLEL_UPDATES = 1


class SteamSensor(StrEnum):
    """Steam sensors."""

    ACCOUNT = "account"
    LAST_ONLINE = "last_online"
    NOW_PLAYING = "now_playing"
    LEVEL = "level"


@dataclass(kw_only=True, frozen=True)
class SteamSensorEntityDescription(SensorEntityDescription):
    """Steam sensor description."""

    value_fn: Callable[[PlayerData], StateType | datetime]
    entity_picture_fn: Callable[[PlayerData, dict[str, str]], str | None] | None = None
    extra_state_attributes_fn: (
        Callable[[PlayerData, dict[str, str]], Mapping[str, Any]] | None
    ) = None


SENSOR_DESCRIPTIONS: tuple[SteamSensorEntityDescription, ...] = (
    SteamSensorEntityDescription(
        key=SteamSensor.ACCOUNT,
        translation_key=SteamSensor.ACCOUNT,
        value_fn=lambda x: STEAM_STATUSES[x.personastate],
        device_class=SensorDeviceClass.ENUM,
        options=list(STEAM_STATUSES.values()),
        entity_picture_fn=lambda x, _: x.avatarfull,
        name=None,
        # Attributes game, game_id, game_image_header, game_image_main, game_icon,
        # last_online, and level are deprecated and can be removed in 2027.2
        extra_state_attributes_fn=lambda x, icons: {
            "real_name": x.realname,
            "created": (
                dt_util.as_local(dt_util.utc_from_timestamp(x.timecreated))
                if x.timecreated is not None
                else None
            ),
            "game": x.gameextrainfo,
            "game_id": x.gameid,
            "game_image_header": (
                f"{STEAM_API_URL}{x.gameid}/{STEAM_HEADER_IMAGE_FILE}"
                if x.gameid is not None
                else None
            ),
            "game_image_main": (
                f"{STEAM_API_URL}{x.gameid}/{STEAM_MAIN_IMAGE_FILE}"
                if x.gameid is not None
                else None
            ),
            "game_icon": (
                f"{STEAM_ICON_URL}{x.gameid}/{info}.jpg"
                if x.gameid is not None and (info := icons.get(x.gameid)) is not None
                else None
            ),
            "last_online": dt_util.utc_from_timestamp(x.lastlogoff),
            "level": x.level,
        },
    ),
    SteamSensorEntityDescription(
        key=SteamSensor.LAST_ONLINE,
        translation_key=SteamSensor.LAST_ONLINE,
        value_fn=(lambda x: dt_util.utc_from_timestamp(x.lastlogoff)),
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SteamSensorEntityDescription(
        key=SteamSensor.NOW_PLAYING,
        translation_key=SteamSensor.NOW_PLAYING,
        value_fn=lambda x: x.gameextrainfo,
        entity_picture_fn=lambda x, icons: (
            f"{STEAM_ICON_URL}{x.gameid}/{game_icon_url}.jpg"
            if x.gameid and (game_icon_url := icons.get(x.gameid))
            else None
        ),
        extra_state_attributes_fn=lambda x, _: {"app_id": x.gameid},
    ),
    SteamSensorEntityDescription(
        key=SteamSensor.LEVEL,
        translation_key=SteamSensor.LEVEL,
        value_fn=lambda x: x.level,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SteamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Steam platform."""
    coordinator = entry.runtime_data
    if TYPE_CHECKING:
        assert entry.unique_id
    async_add_entities(
        SteamSensorEntity(coordinator, entry.unique_id, description)
        for description in SENSOR_DESCRIPTIONS
        if entry.unique_id in coordinator.data
    )

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_FRIEND):
        async_add_entities(
            [
                SteamSensorEntity(coordinator, subentry.unique_id, description)
                for description in SENSOR_DESCRIPTIONS
                if subentry.unique_id in coordinator.data
            ],
            config_subentry_id=subentry.subentry_id,
        )


class SteamSensorEntity(SteamEntity, SensorEntity):
    """Representation of a Steam sensor entity."""

    entity_description: SteamSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._steamid])

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        return (
            fn(self.coordinator.data[self._steamid], self.coordinator.game_icons)
            if (fn := self.entity_description.entity_picture_fn) is not None
            else super().entity_picture
        )

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the sensor."""
        return (
            fn(self.coordinator.data[self._steamid], self.coordinator.game_icons)
            if (fn := self.entity_description.extra_state_attributes_fn) is not None
            else super().extra_state_attributes
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._steamid in self.coordinator.data
