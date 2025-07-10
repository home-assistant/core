"""Sensor platform for PlayStation Network integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import ASSETS_PATH, CONF_SHOW_ENTITY_PICTURES
from .coordinator import PlaystationNetworkConfigEntry, PlaystationNetworkData
from .entity import PlaystationNetworkServiceEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkSensorEntityDescription(SensorEntityDescription):
    """PlayStation Network sensor description."""

    value_fn: Callable[[PlaystationNetworkData], StateType | datetime]
    available_fn: Callable[[PlaystationNetworkData], bool] = lambda _: True
    entity_picture: Callable[[PlaystationNetworkData], str | None] | str | None = None


class PlaystationNetworkSensor(StrEnum):
    """PlayStation Network sensors."""

    TROPHY_LEVEL = "trophy_level"
    TROPHY_LEVEL_PROGRESS = "trophy_level_progress"
    EARNED_TROPHIES_PLATINUM = "earned_trophies_platinum"
    EARNED_TROPHIES_GOLD = "earned_trophies_gold"
    EARNED_TROPHIES_SILVER = "earned_trophies_silver"
    EARNED_TROPHIES_BRONZE = "earned_trophies_bronze"
    ONLINE_ID = "online_id"
    LAST_ONLINE = "last_online"
    ONLINE_STATUS = "online_status"


SENSOR_DESCRIPTIONS: tuple[PlaystationNetworkSensorEntityDescription, ...] = (
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.TROPHY_LEVEL,
        translation_key=PlaystationNetworkSensor.TROPHY_LEVEL,
        value_fn=(
            lambda psn: psn.trophy_summary.trophy_level if psn.trophy_summary else None
        ),
        entity_picture=(
            lambda psn: f"{ASSETS_PATH}/tier_{psn.trophy_summary.tier}.png"
            if psn.trophy_summary
            else None
        ),
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.TROPHY_LEVEL_PROGRESS,
        translation_key=PlaystationNetworkSensor.TROPHY_LEVEL_PROGRESS,
        value_fn=(
            lambda psn: psn.trophy_summary.progress if psn.trophy_summary else None
        ),
        native_unit_of_measurement=PERCENTAGE,
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_PLATINUM,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_PLATINUM,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.platinum
            if psn.trophy_summary
            else None
        ),
        entity_picture=f"{ASSETS_PATH}/platinum.png",
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_GOLD,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_GOLD,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.gold
            if psn.trophy_summary
            else None
        ),
        entity_picture=f"{ASSETS_PATH}/gold.png",
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_SILVER,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_SILVER,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.silver
            if psn.trophy_summary
            else None
        ),
        entity_picture=f"{ASSETS_PATH}/silver.png",
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_BRONZE,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_BRONZE,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.bronze
            if psn.trophy_summary
            else None
        ),
        entity_picture=f"{ASSETS_PATH}/bronze.png",
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.ONLINE_ID,
        translation_key=PlaystationNetworkSensor.ONLINE_ID,
        value_fn=lambda psn: psn.username,
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.LAST_ONLINE,
        translation_key=PlaystationNetworkSensor.LAST_ONLINE,
        value_fn=(
            lambda psn: dt_util.parse_datetime(
                psn.presence["basicPresence"]["lastAvailableDate"]
            )
        ),
        available_fn=lambda psn: "lastAvailableDate" in psn.presence["basicPresence"],
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.ONLINE_STATUS,
        translation_key=PlaystationNetworkSensor.ONLINE_STATUS,
        value_fn=lambda psn: psn.availability.lower().replace("unavailable", "offline"),
        device_class=SensorDeviceClass.ENUM,
        options=["offline", "availabletoplay", "availabletocommunicate", "busy"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PlaystationNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        PlaystationNetworkSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class PlaystationNetworkSensorEntity(
    PlaystationNetworkServiceEntity,
    SensorEntity,
):
    """Representation of a PlayStation Network sensor entity."""

    entity_description: PlaystationNetworkSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if self.entity_description.key is PlaystationNetworkSensor.ONLINE_ID and (
            profile_pictures := self.coordinator.data.profile.get(
                "personalDetail", {}
            ).get("profilePictures")
        ):
            return next(
                (pic.get("url") for pic in profile_pictures if pic.get("size") == "xl"),
                None,
            )

        if (
            self.coordinator.config_entry.options.get(CONF_SHOW_ENTITY_PICTURES)
            and (entity_picture := self.entity_description.entity_picture) is not None
        ):
            return (
                entity_picture(self.coordinator.data)
                if callable(entity_picture)
                else entity_picture
            )
        return super().entity_picture

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return (
            self.entity_description.available_fn(self.coordinator.data)
            and super().available
        )
