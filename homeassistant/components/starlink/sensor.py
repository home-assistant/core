"""Contains sensors exposed by the Starlink integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import StarlinkData, StarlinkUpdateCoordinator
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all sensors for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkSensorEntity(coordinator, description) for description in SENSORS
    )


@dataclass
class StarlinkSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[StarlinkData], datetime | StateType]


@dataclass
class StarlinkSensorEntityDescription(
    SensorEntityDescription, StarlinkSensorEntityDescriptionMixin
):
    """Describes a Starlink sensor entity."""


class StarlinkSensorEntity(StarlinkEntity, SensorEntity):
    """A SensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkSensorEntityDescription

    def __init__(
        self,
        coordinator: StarlinkUpdateCoordinator,
        description: StarlinkSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.coordinator.data.status['id']}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)


SENSORS: tuple[StarlinkSensorEntityDescription, ...] = (
    StarlinkSensorEntityDescription(
        key="ping",
        name="Ping",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        value_fn=lambda data: round(data.status["pop_ping_latency_ms"]),
    ),
    StarlinkSensorEntityDescription(
        key="azimuth",
        name="Azimuth",
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: round(data.status["direction_azimuth"]),
    ),
    StarlinkSensorEntityDescription(
        key="elevation",
        name="Elevation",
        icon="mdi:compass",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: round(data.status["direction_elevation"]),
    ),
    StarlinkSensorEntityDescription(
        key="uplink_throughput",
        name="Uplink throughput",
        icon="mdi:upload",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        value_fn=lambda data: round(data.status["uplink_throughput_bps"]),
    ),
    StarlinkSensorEntityDescription(
        key="downlink_throughput",
        name="Downlink throughput",
        icon="mdi:download",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        value_fn=lambda data: round(data.status["downlink_throughput_bps"]),
    ),
    StarlinkSensorEntityDescription(
        key="last_boot_time",
        name="Last boot time",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: datetime.now().astimezone()
        - timedelta(seconds=data.status["uptime"]),
    ),
)
