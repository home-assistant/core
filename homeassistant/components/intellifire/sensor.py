"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from intellifire4py import IntellifirePollData

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
from .coordinator import IntellifireDataUpdateCoordinator
from .entity import IntellifireEntity


@dataclass
class IntellifireSensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[IntellifirePollData], int | str | datetime | None]


@dataclass
class IntellifireSensorEntityDescription(
    SensorEntityDescription,
    IntellifireSensorRequiredKeysMixin,
):
    """Describes a sensor entity."""


def _time_remaining_to_timestamp(data: IntellifirePollData) -> datetime | None:
    """Define a sensor that takes into account timezone."""
    if not (seconds_offset := data.timeremaining_s):
        return None
    return utcnow() + timedelta(seconds=seconds_offset)


def _downtime_to_timestamp(data: IntellifirePollData) -> datetime | None:
    """Define a sensor that takes into account a timezone."""
    if not (seconds_offset := data.downtime):
        return None
    return utcnow() - timedelta(seconds=seconds_offset)


INTELLIFIRE_SENSORS: tuple[IntellifireSensorEntityDescription, ...] = (
    IntellifireSensorEntityDescription(
        key="flame_height",
        icon="mdi:fire-circle",
        name="Flame Height",
        state_class=SensorStateClass.MEASUREMENT,
        # UI uses 1-5 for flame height, backing lib uses 0-4
        value_fn=lambda data: (data.flameheight + 1),
    ),
    IntellifireSensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.temperature_c,
    ),
    IntellifireSensorEntityDescription(
        key="target_temp",
        name="Target Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.thermostat_setpoint_c,
    ),
    IntellifireSensorEntityDescription(
        key="fan_speed",
        icon="mdi:fan",
        name="Fan Speed",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.fanspeed,
    ),
    IntellifireSensorEntityDescription(
        key="timer_end_timestamp",
        icon="mdi:timer-sand",
        name="Timer End",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_time_remaining_to_timestamp,
    ),
    IntellifireSensorEntityDescription(
        key="downtime",
        name="Downtime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_downtime_to_timestamp,
    ),
    IntellifireSensorEntityDescription(
        key="uptime",
        name="Uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: utcnow() - timedelta(seconds=data.uptime),
    ),
    IntellifireSensorEntityDescription(
        key="connection_quality",
        name="Connection Quality",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.connection_quality,
        entity_registry_enabled_default=False,
    ),
    IntellifireSensorEntityDescription(
        key="ecm_latency",
        name="ECM Latency",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.ecm_latency,
        entity_registry_enabled_default=False,
    ),
    IntellifireSensorEntityDescription(
        key="ipv4_address",
        name="IP",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.ipv4_address,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Define setup entry call."""

    coordinator: IntellifireDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IntellifireSensor(coordinator=coordinator, description=description)
        for description in INTELLIFIRE_SENSORS
    )


class IntellifireSensor(IntellifireEntity, SensorEntity):
    """Extends IntellifireEntity with Sensor specific logic."""

    entity_description: IntellifireSensorEntityDescription

    @property
    def native_value(self) -> int | str | datetime | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.read_api.data)
