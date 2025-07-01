"""Sensor platform for PlayStation Network integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    PlaystationNetworkConfigEntry,
    PlaystationNetworkCoordinator,
    PlaystationNetworkData,
)

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class PlaystationNetworkSensorEntityDescription(SensorEntityDescription):
    """PlayStation Network sensor description."""

    value_fn: Callable[[PlaystationNetworkData], StateType | datetime]
    entity_picture: str | None = None
    available_fn: Callable[[PlaystationNetworkData], bool] = lambda _: True


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


SENSOR_DESCRIPTIONS: tuple[PlaystationNetworkSensorEntityDescription, ...] = (
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.TROPHY_LEVEL,
        translation_key=PlaystationNetworkSensor.TROPHY_LEVEL,
        value_fn=(
            lambda psn: psn.trophy_summary.trophy_level if psn.trophy_summary else None
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
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_GOLD,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_GOLD,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.gold
            if psn.trophy_summary
            else None
        ),
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_SILVER,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_SILVER,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.silver
            if psn.trophy_summary
            else None
        ),
    ),
    PlaystationNetworkSensorEntityDescription(
        key=PlaystationNetworkSensor.EARNED_TROPHIES_BRONZE,
        translation_key=PlaystationNetworkSensor.EARNED_TROPHIES_BRONZE,
        value_fn=(
            lambda psn: psn.trophy_summary.earned_trophies.bronze
            if psn.trophy_summary
            else None
        ),
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
    CoordinatorEntity[PlaystationNetworkCoordinator], SensorEntity
):
    """Representation of a PlayStation Network sensor entity."""

    entity_description: PlaystationNetworkSensorEntityDescription
    coordinator: PlaystationNetworkCoordinator

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PlaystationNetworkCoordinator,
        description: PlaystationNetworkSensorEntityDescription,
    ) -> None:
        """Initialize a sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            name=coordinator.data.username,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Sony Interactive Entertainment",
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""
        if self.entity_description.key is PlaystationNetworkSensor.ONLINE_ID and (
            profile_pictures := self.coordinator.data.profile["personalDetail"].get(
                "profilePictures"
            )
        ):
            return next(
                (pic.get("url") for pic in profile_pictures if pic.get("size") == "xl"),
                None,
            )

        return super().entity_picture

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        return (
            self.entity_description.available_fn(self.coordinator.data)
            and super().available
        )
