"""Platform for sensor integration for squeezebox."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SqueezeboxConfigEntry
from .const import (
    PLAYER_SENSOR_NEXT_ALARM,
    SIGNAL_PLAYER_DISCOVERED,
    STATUS_SENSOR_INFO_TOTAL_ALBUMS,
    STATUS_SENSOR_INFO_TOTAL_ARTISTS,
    STATUS_SENSOR_INFO_TOTAL_DURATION,
    STATUS_SENSOR_INFO_TOTAL_GENRES,
    STATUS_SENSOR_INFO_TOTAL_SONGS,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_OTHER_PLAYER_COUNT,
    STATUS_SENSOR_PLAYER_COUNT,
)
from .entity import LMSStatusEntity, SqueezeboxEntity, SqueezeBoxPlayerUpdateCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SERVER_STATUS_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_ALBUMS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_ARTISTS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_DURATION,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_GENRES,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_INFO_TOTAL_SONGS,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_LASTSCAN,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_PLAYER_COUNT,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key=STATUS_SENSOR_OTHER_PLAYER_COUNT,
        state_class=SensorStateClass.TOTAL,
        entity_registry_visible_default=False,
    ),
)


@dataclass(frozen=True, kw_only=True)
class PlayerSensorEntityDescription(SensorEntityDescription):
    """Describes player sensor entity."""

    value_fn: Callable[[SqueezeboxSensorEntity], datetime | None]


PLAYER_SENSORS: tuple[PlayerSensorEntityDescription, ...] = (
    PlayerSensorEntityDescription(
        key=PLAYER_SENSOR_NEXT_ALARM,
        translation_key=PLAYER_SENSOR_NEXT_ALARM,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sensor: sensor.coordinator.player.alarm_next,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    # Add player sensor entities when player discovered
    async def _player_discovered(
        player_coordinator: SqueezeBoxPlayerUpdateCoordinator,
    ) -> None:
        _LOGGER.debug(
            "Setting up sensor entities for player %s, model %s",
            player_coordinator.player.name,
            player_coordinator.player.model,
        )

        async_add_entities(
            SqueezeboxSensorEntity(player_coordinator, description)
            for description in PLAYER_SENSORS
        )

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_PLAYER_DISCOVERED}{entry.entry_id}", _player_discovered
        )
    )

    async_add_entities(
        ServerStatusSensor(entry.runtime_data.coordinator, description)
        for description in SERVER_STATUS_SENSORS
    )


class ServerStatusSensor(LMSStatusEntity, SensorEntity):
    """LMS Status based sensor from LMS via coordinator."""

    @property
    def native_value(self) -> StateType:
        """LMS Status directly from coordinator data."""
        return cast(StateType, self.coordinator.data[self.entity_description.key])


class SqueezeboxSensorEntity(SqueezeboxEntity, SensorEntity):
    """Representation of player based sensors."""

    entity_description: PlayerSensorEntityDescription

    def __init__(
        self,
        coordinator: SqueezeBoxPlayerUpdateCoordinator,
        description: PlayerSensorEntityDescription,
    ) -> None:
        """Initialize the SqueezeBox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{format_mac(self._player.player_id)}_{description.key}"

    @property
    def native_value(self) -> datetime | None:
        """Sensor value directly from player coordinator."""
        return self.entity_description.value_fn(self)
