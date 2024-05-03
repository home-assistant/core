"""Support for Hydrawise sprinkler sensors."""

from __future__ import annotations

from datetime import datetime

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

FLOW_CONTROLLER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="daily_total_water_use",
        translation_key="daily_total_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="daily_inactive_water_use",
        translation_key="daily_inactive_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
)

FLOW_ZONE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
)

ZONE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        translation_key="next_cycle",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="watering_time",
        translation_key="watering_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
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
            HydrawiseSensor(coordinator, description, controller, zone=zone)
            for zone in controller.zones
            for description in ZONE_SENSORS
        )
        entities.extend(
            HydrawiseSensor(coordinator, description, controller, sensor=sensor)
            for sensor in controller.sensors
            for description in FLOW_CONTROLLER_SENSORS
            if "flow meter" in sensor.model.name.lower()
        )
        entities.extend(
            HydrawiseSensor(
                coordinator, description, controller, zone=zone, sensor=sensor
            )
            for zone in controller.zones
            for sensor in controller.sensors
            for description in FLOW_ZONE_SENSORS
            if "flow meter" in sensor.model.name.lower()
        )
    async_add_entities(entities)


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    @property
    def icon(self) -> str | None:
        """Icon of the entity based on the value."""
        if self.entity_description.key in FLOW_MEASUREMENT_KEYS and self.state < 0.01:
            return "mdi:water-outline"
        return None

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_native_value = getattr(self, f"_get_{self.entity_description.key}")()

    def _get_watering_time(self) -> int:
        assert self.zone is not None
        if (current_run := self.zone.scheduled_runs.current_run) is not None:
            return int(current_run.remaining_time.total_seconds() / 60)
        return 0

    def _get_next_cycle(self) -> datetime:
        assert self.zone is not None
        if (next_run := self.zone.scheduled_runs.next_run) is not None:
            return dt_util.as_utc(next_run.start_time)
        return datetime.max.replace(tzinfo=dt_util.UTC)

    def _get_daily_active_water_use(self) -> float:
        daily_water_summary = self.coordinator.data.daily_water_use[self.controller.id]
        if self.zone is not None:
            # water use for the zone
            return float(
                daily_water_summary.active_use_by_zone_id.get(self.zone.id, 0.0)
            )
        if self.sensor is not None:
            # water use for the controller
            return daily_water_summary.total_active_use
        return 0.0  # pragma: no cover

    def _get_daily_inactive_water_use(self) -> float | None:
        if self.zone is None and self.sensor is not None:
            # water use for the controller
            daily_water_summary = self.coordinator.data.daily_water_use[
                self.controller.id
            ]
            return daily_water_summary.total_inactive_use
        return None  # pragma: no cover

    def _get_daily_total_water_use(self) -> float | None:
        if self.zone is None and self.sensor is not None:
            # water use for the controller
            daily_water_summary = self.coordinator.data.daily_water_use[
                self.controller.id
            ]
            return daily_water_summary.total_use
        return None  # pragma: no cover
