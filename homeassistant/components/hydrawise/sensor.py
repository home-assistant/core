"""Support for Hydrawise sprinkler sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity


@dataclass(frozen=True, kw_only=True)
class HydrawiseSensorEntityDescription(SensorEntityDescription):
    """Describes Hydrawise binary sensor."""

    value_fn: Callable[[HydrawiseSensor], Any]


def _get_zone_watering_time(sensor: HydrawiseSensor) -> int:
    if (current_run := sensor.zone.scheduled_runs.current_run) is not None:
        return int(current_run.remaining_time.total_seconds() / 60)
    return 0


def _get_zone_next_cycle(sensor: HydrawiseSensor) -> datetime | None:
    if (next_run := sensor.zone.scheduled_runs.next_run) is not None:
        return dt_util.as_utc(next_run.start_time)
    return None


def _get_zone_daily_active_water_use(sensor: HydrawiseSensor) -> float:
    """Get active water use for the zone."""
    daily_water_summary = sensor.coordinator.data.daily_water_use[sensor.controller.id]
    return float(daily_water_summary.active_use_by_zone_id.get(sensor.zone.id, 0.0))


def _get_controller_daily_active_water_use(sensor: HydrawiseSensor) -> float:
    """Get active water use for the controller."""
    daily_water_summary = sensor.coordinator.data.daily_water_use[sensor.controller.id]
    return daily_water_summary.total_active_use


def _get_controller_daily_inactive_water_use(sensor: HydrawiseSensor) -> float | None:
    """Get inactive water use for the controller."""
    daily_water_summary = sensor.coordinator.data.daily_water_use[sensor.controller.id]
    return daily_water_summary.total_inactive_use


def _get_controller_daily_total_water_use(sensor: HydrawiseSensor) -> float | None:
    """Get inactive water use for the controller."""
    daily_water_summary = sensor.coordinator.data.daily_water_use[sensor.controller.id]
    return daily_water_summary.total_use


FLOW_CONTROLLER_SENSORS: tuple[HydrawiseSensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="daily_total_water_use",
        translation_key="daily_total_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=_get_controller_daily_total_water_use,
    ),
    HydrawiseSensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=_get_controller_daily_active_water_use,
    ),
    HydrawiseSensorEntityDescription(
        key="daily_inactive_water_use",
        translation_key="daily_inactive_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=_get_controller_daily_inactive_water_use,
    ),
)

FLOW_ZONE_SENSORS: tuple[SensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=_get_zone_daily_active_water_use,
    ),
)

ZONE_SENSORS: tuple[HydrawiseSensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="next_cycle",
        translation_key="next_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_get_zone_next_cycle,
    ),
    HydrawiseSensorEntityDescription(
        key="watering_time",
        translation_key="watering_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_get_zone_watering_time,
    ),
)

FLOW_MEASUREMENT_KEYS = [x.key for x in FLOW_CONTROLLER_SENSORS]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hydrawise sensor platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[HydrawiseSensor] = []
    for controller in coordinator.data.controllers.values():
        entities.extend(
            HydrawiseSensor(coordinator, description, controller, zone_id=zone.id)
            for zone in controller.zones
            for description in ZONE_SENSORS
        )
        entities.extend(
            HydrawiseSensor(coordinator, description, controller, sensor_id=sensor.id)
            for sensor in controller.sensors
            for description in FLOW_CONTROLLER_SENSORS
            if "flow meter" in sensor.model.name.lower()
        )
        entities.extend(
            HydrawiseSensor(
                coordinator,
                description,
                controller,
                zone_id=zone.id,
                sensor_id=sensor.id,
            )
            for zone in controller.zones
            for sensor in controller.sensors
            for description in FLOW_ZONE_SENSORS
            if "flow meter" in sensor.model.name.lower()
        )
    async_add_entities(entities)


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    entity_description: HydrawiseSensorEntityDescription

    @property
    def icon(self) -> str | None:
        """Icon of the entity based on the value."""
        if (
            self.entity_description.key in FLOW_MEASUREMENT_KEYS
            and round(self.state, 2) == 0.0
        ):
            return "mdi:water-outline"
        return None

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_native_value = self.entity_description.value_fn(self)
