"""Platform for sensor integration."""

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
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .coordinator import IntelliFireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass(frozen=True)
class IntelliFireSensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[
        [IntelliFireDataUpdateCoordinator], int | str | datetime | float | None
    ]


@dataclass(frozen=True)
class IntelliFireSensorEntityDescription(
    SensorEntityDescription,
    IntelliFireSensorRequiredKeysMixin,
):
    """Describes a sensor entity."""


def _time_remaining_to_timestamp(
    coordinator: IntelliFireDataUpdateCoordinator,
) -> datetime | None:
    """Define a sensor that takes into account timezone."""
    if not (seconds_offset := coordinator.data.timeremaining_s):
        return None
    return utcnow() + timedelta(seconds=seconds_offset)


def _downtime_to_timestamp(
    coordinator: IntelliFireDataUpdateCoordinator,
) -> datetime | None:
    """Define a sensor that takes into account a timezone."""
    if not (seconds_offset := coordinator.data.downtime):
        return None
    return utcnow() - timedelta(seconds=seconds_offset)


def _uptime_to_timestamp(
    coordinator: IntelliFireDataUpdateCoordinator,
) -> datetime | None:
    """Return a timestamp of how long the sensor has been up."""
    if not (seconds_offset := coordinator.data.uptime):
        return None
    return utcnow() - timedelta(seconds=seconds_offset)


INTELLIFIRE_SENSORS: tuple[IntelliFireSensorEntityDescription, ...] = (
    IntelliFireSensorEntityDescription(
        key="flame_height",
        translation_key="flame_height",
        state_class=SensorStateClass.MEASUREMENT,
        # UI uses 1-5 for flame height, backing lib uses 0-4
        value_fn=lambda coordinator: (coordinator.data.flameheight + 1),
    ),
    IntelliFireSensorEntityDescription(
        key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: coordinator.data.temperature_c,
    ),
    IntelliFireSensorEntityDescription(
        key="target_temp",
        translation_key="target_temp",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coordinator: coordinator.data.thermostat_setpoint_c,
    ),
    IntelliFireSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.data.fanspeed,
    ),
    IntelliFireSensorEntityDescription(
        key="timer_end_timestamp",
        translation_key="timer_end_timestamp",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_time_remaining_to_timestamp,
    ),
    IntelliFireSensorEntityDescription(
        key="downtime",
        translation_key="downtime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_downtime_to_timestamp,
    ),
    IntelliFireSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_uptime_to_timestamp,
    ),
    IntelliFireSensorEntityDescription(
        key="connection_quality",
        translation_key="connection_quality",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.connection_quality,
        entity_registry_enabled_default=False,
    ),
    IntelliFireSensorEntityDescription(
        key="ecm_latency",
        translation_key="ecm_latency",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.ecm_latency,
        entity_registry_enabled_default=False,
    ),
    IntelliFireSensorEntityDescription(
        key="ipv4_address",
        translation_key="ipv4_address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.data.ipv4_address,
    ),
    # HACS DIAGNOSTIC SENSORS
    IntelliFireSensorEntityDescription(
        key="local_connectivity",
        translation_key="local_connectivity",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.fireplace.local_connectivity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Define setup entry call."""

    coordinator: IntelliFireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntelliFireSensor(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_SENSORS
    )


class IntelliFireSensor(IntellifireEntity, SensorEntity):
    """Extends IntelliFireEntity with Sensor specific logic."""

    entity_description: IntelliFireSensorEntityDescription

    @property
    def native_value(self) -> int | str | datetime | float | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator)
