"""Support for Hydrawise sprinkler sensors."""

from __future__ import annotations

from datetime import datetime

from pydrawise.schema import ControllerWaterUseSummary, Zone

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
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="daily_inactive_water_use",
        translation_key="daily_inactive_water_use",
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
)

FLOW_ZONE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="daily_active_water_use",
        translation_key="daily_active_water_use",
        icon="mdi:water-pump",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
    ),
)

ZONE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        translation_key="next_cycle",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="watering_time",
        translation_key="watering_time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
)

SENSOR_KEYS: list[str] = [
    desc.key
    for desc in (
        *FLOW_CONTROLLER_SENSORS,
        *FLOW_ZONE_SENSORS,
        *ZONE_SENSORS,
    )
]

TWO_YEAR_SECONDS = 60 * 60 * 24 * 365 * 2
WATERING_TIME_ICON = "mdi:water-pump"


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

    zone: Zone

    def _update_attrs(self) -> None:
        """Update state attributes."""
        if self.entity_description.key == "watering_time":
            if (current_run := self.zone.scheduled_runs.current_run) is not None:
                self._attr_native_value = int(
                    current_run.remaining_time.total_seconds() / 60
                )
            else:
                self._attr_native_value = 0
        elif self.entity_description.key == "next_cycle":
            if (next_run := self.zone.scheduled_runs.next_run) is not None:
                self._attr_native_value = dt_util.as_utc(next_run.start_time)
            else:
                self._attr_native_value = datetime.max.replace(tzinfo=dt_util.UTC)
        elif self.entity_description.key == "daily_active_water_use":
            daily_water_summary = self.coordinator.data.daily_water_use.get(
                self.controller.id, ControllerWaterUseSummary()
            )
            if self.zone is None and self.sensor is not None:
                # water use for the controller
                self._attr_native_value = daily_water_summary.total_active_use
            elif self.zone is not None:
                # water use for the zone
                self._attr_native_value = daily_water_summary.active_use_by_zone_id.get(
                    self.zone.id, 0.0
                )
            else:
                self._attr_native_value = 0
        elif (
            self.entity_description.key
            in ("daily_inactive_water_use", "daily_total_water_use")
            and self.zone is None
            and self.sensor is not None
        ):
            # water use for the controller
            daily_water_summary = self.coordinator.data.daily_water_use.get(
                self.controller.id, ControllerWaterUseSummary()
            )
            self._attr_native_value = (
                daily_water_summary.total_inactive_use
                if self.entity_description.key == "daily_inactive_water_use"
                else daily_water_summary.total_use
            )
