"""Support for Hydrawise sprinkler sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pydrawise.schema import ControllerWaterUseSummary

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import HydrawiseConfigEntry
from .entity import HydrawiseEntity


@dataclass(frozen=True, kw_only=True)
class HydrawiseSensorEntityDescription(SensorEntityDescription):
    """Describes Hydrawise binary sensor."""

    value_fn: Callable[[HydrawiseSensor], Any]


def _get_water_use(sensor: HydrawiseSensor) -> ControllerWaterUseSummary:
    return sensor.coordinator.data.daily_water_summary[sensor.controller.id]


WATER_USE_CONTROLLER_SENSORS: tuple[HydrawiseSensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="daily_active_water_time",
        translation_key="daily_active_water_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda sensor: _get_water_use(
            sensor
        ).total_active_time.total_seconds(),
    ),
)


WATER_USE_ZONE_SENSORS: tuple[HydrawiseSensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="daily_active_water_time",
        translation_key="daily_active_water_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda sensor: (
            _get_water_use(sensor)
            .active_time_by_zone_id.get(sensor.zone.id, timedelta())
            .total_seconds()
        ),
    ),
)

FLOW_CONTROLLER_SENSORS: tuple[HydrawiseSensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="daily_total_water_use",
        translation_key="daily_total_water_use",
        device_class=SensorDeviceClass.VOLUME,
        suggested_display_precision=1,
        value_fn=lambda sensor: _get_water_use(sensor).total_use,
    ),
    HydrawiseSensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        device_class=SensorDeviceClass.VOLUME,
        suggested_display_precision=1,
        value_fn=lambda sensor: _get_water_use(sensor).total_active_use,
    ),
    HydrawiseSensorEntityDescription(
        key="daily_inactive_water_use",
        translation_key="daily_inactive_water_use",
        device_class=SensorDeviceClass.VOLUME,
        suggested_display_precision=1,
        value_fn=lambda sensor: _get_water_use(sensor).total_inactive_use,
    ),
)

FLOW_ZONE_SENSORS: tuple[SensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        device_class=SensorDeviceClass.VOLUME,
        suggested_display_precision=1,
        value_fn=lambda sensor: float(
            _get_water_use(sensor).active_use_by_zone_id.get(sensor.zone.id, 0.0)
        ),
    ),
)

ZONE_SENSORS: tuple[HydrawiseSensorEntityDescription, ...] = (
    HydrawiseSensorEntityDescription(
        key="next_cycle",
        translation_key="next_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sensor: (
            dt_util.as_utc(sensor.zone.scheduled_runs.next_run.start_time)
            if sensor.zone.scheduled_runs.next_run is not None
            else None
        ),
    ),
    HydrawiseSensorEntityDescription(
        key="watering_time",
        translation_key="watering_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda sensor: (
            int(
                sensor.zone.scheduled_runs.current_run.remaining_time.total_seconds()
                / 60
            )
            if sensor.zone.scheduled_runs.current_run is not None
            else 0
        ),
    ),
)

FLOW_MEASUREMENT_KEYS = [x.key for x in FLOW_CONTROLLER_SENSORS]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HydrawiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydrawise sensor platform."""
    coordinators = config_entry.runtime_data
    entities: list[HydrawiseSensor] = []
    for controller in coordinators.main.data.controllers.values():
        entities.extend(
            HydrawiseSensor(coordinators.water_use, description, controller)
            for description in WATER_USE_CONTROLLER_SENSORS
        )
        entities.extend(
            HydrawiseSensor(
                coordinators.water_use, description, controller, zone_id=zone.id
            )
            for zone in controller.zones
            for description in WATER_USE_ZONE_SENSORS
        )
        entities.extend(
            HydrawiseSensor(coordinators.main, description, controller, zone_id=zone.id)
            for zone in controller.zones
            for description in ZONE_SENSORS
        )
        if (
            coordinators.water_use.data.daily_water_summary[controller.id].total_use
            is not None
        ):
            # we have a flow sensor for this controller
            entities.extend(
                HydrawiseSensor(coordinators.water_use, description, controller)
                for description in FLOW_CONTROLLER_SENSORS
            )
            entities.extend(
                HydrawiseSensor(
                    coordinators.water_use,
                    description,
                    controller,
                    zone_id=zone.id,
                )
                for zone in controller.zones
                for description in FLOW_ZONE_SENSORS
            )
    async_add_entities(entities)


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    entity_description: HydrawiseSensorEntityDescription

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit_of_measurement of the sensor."""
        if self.entity_description.device_class != SensorDeviceClass.VOLUME:
            return self.entity_description.native_unit_of_measurement
        return (
            UnitOfVolume.GALLONS
            if self.coordinator.data.user.units.units_name == "imperial"
            else UnitOfVolume.LITERS
        )

    @property
    def icon(self) -> str | None:
        """Icon of the entity based on the value."""
        if (
            self.entity_description.key in FLOW_MEASUREMENT_KEYS
            and self.entity_description.device_class == SensorDeviceClass.VOLUME
            and round(self.state, 2) == 0.0
        ):
            return "mdi:water-outline"
        return None

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_native_value = self.entity_description.value_fn(self)
