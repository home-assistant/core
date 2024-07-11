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
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfDataRate,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import now

from .const import DOMAIN
from .coordinator import StarlinkData
from .entity import StarlinkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up all sensors for this entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        StarlinkSensorEntity(coordinator, description) for description in SENSORS
    )


@dataclass(frozen=True, kw_only=True)
class StarlinkSensorEntityDescription(SensorEntityDescription):
    """Describes a Starlink sensor entity."""

    value_fn: Callable[[StarlinkData], datetime | StateType]


class StarlinkSensorEntity(StarlinkEntity, SensorEntity):
    """A SensorEntity for Starlink devices. Handles creating unique IDs."""

    entity_description: StarlinkSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Calculate the sensor value from the entity description."""
        return self.entity_description.value_fn(self.coordinator.data)


SENSORS: tuple[StarlinkSensorEntityDescription, ...] = (
    StarlinkSensorEntityDescription(
        key="ping",
        translation_key="ping",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["pop_ping_latency_ms"],
    ),
    StarlinkSensorEntityDescription(
        key="azimuth",
        translation_key="azimuth",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["direction_azimuth"],
    ),
    StarlinkSensorEntityDescription(
        key="elevation",
        translation_key="elevation",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["direction_elevation"],
    ),
    StarlinkSensorEntityDescription(
        key="uplink_throughput",
        translation_key="uplink_throughput",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["uplink_throughput_bps"],
    ),
    StarlinkSensorEntityDescription(
        key="downlink_throughput",
        translation_key="downlink_throughput",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_display_precision=0,
        value_fn=lambda data: data.status["downlink_throughput_bps"],
    ),
    StarlinkSensorEntityDescription(
        key="last_boot_time",
        translation_key="last_boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: now() - timedelta(seconds=data.status["uptime"]),
    ),
    StarlinkSensorEntityDescription(
        key="ping_drop_rate",
        translation_key="ping_drop_rate",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.status["pop_ping_drop_rate"] * 100,
    ),
)
