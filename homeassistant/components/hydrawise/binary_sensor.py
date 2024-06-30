"""Support for Hydrawise sprinkler binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydrawise import Zone
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from .const import (
    DOMAIN,
    LOGGER,
    MAX_WATERING_TIME,
    SERVICE_RESUME,
    SERVICE_START_WATERING,
    SERVICE_SUSPEND,
)
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity


@dataclass(frozen=True, kw_only=True)
class HydrawiseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Hydrawise binary sensor."""

    value_fn: Callable[[HydrawiseBinarySensor], bool | None]
    always_available: bool = False


CONTROLLER_BINARY_SENSORS: tuple[HydrawiseBinarySensorEntityDescription, ...] = (
    HydrawiseBinarySensorEntityDescription(
        key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=(
            lambda status_sensor: status_sensor.coordinator.last_update_success
            and status_sensor.controller.online
        ),
        # Connectivtiy sensor is always available
        always_available=True,
    ),
)

RAIN_SENSOR_BINARY_SENSOR: tuple[HydrawiseBinarySensorEntityDescription, ...] = (
    HydrawiseBinarySensorEntityDescription(
        key="rain_sensor",
        translation_key="rain_sensor",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda rain_sensor: rain_sensor.sensor.status.active,
    ),
)

ZONE_BINARY_SENSORS: tuple[HydrawiseBinarySensorEntityDescription, ...] = (
    HydrawiseBinarySensorEntityDescription(
        key="is_watering",
        translation_key="watering",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=(
            lambda watering_sensor: watering_sensor.zone.scheduled_runs.current_run
            is not None
        ),
    ),
)

SCHEMA_START_WATERING: VolDictType = {
    vol.Optional("duration"): cv.positive_time_period,
}
SCHEMA_SUSPEND: VolDictType = {
    vol.Required("until"): cv.datetime,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hydrawise binary_sensor platform."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[HydrawiseBinarySensor] = []
    for controller in coordinator.data.controllers.values():
        entities.extend(
            HydrawiseBinarySensor(coordinator, description, controller)
            for description in CONTROLLER_BINARY_SENSORS
        )
        entities.extend(
            HydrawiseBinarySensor(
                coordinator,
                description,
                controller,
                sensor_id=sensor.id,
            )
            for sensor in controller.sensors
            for description in RAIN_SENSOR_BINARY_SENSOR
            if "rain sensor" in sensor.model.name.lower()
        )
        entities.extend(
            HydrawiseZoneBinarySensor(
                coordinator, description, controller, zone_id=zone.id
            )
            for zone in controller.zones
            for description in ZONE_BINARY_SENSORS
        )
    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(SERVICE_RESUME, {}, "resume")
    platform.async_register_entity_service(
        SERVICE_START_WATERING, SCHEMA_START_WATERING, "start_watering"
    )
    platform.async_register_entity_service(SERVICE_SUSPEND, SCHEMA_SUSPEND, "suspend")


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    entity_description: HydrawiseBinarySensorEntityDescription

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_is_on = self.entity_description.value_fn(self)

    @property
    def available(self) -> bool:
        """Set the entity availability."""
        if self.entity_description.always_available:
            return True
        return super().available


class HydrawiseZoneBinarySensor(HydrawiseBinarySensor):
    """A sensor implementation for a Hydrawise irrigation zone."""

    zone: Zone

    async def start_watering(self, duration: timedelta | None = None) -> None:
        """Start watering in the irrigation zone."""
        if duration is None:
            duration = timedelta(minutes=0)
        if duration > MAX_WATERING_TIME:
            LOGGER.warning("Clamping watering time to %s", MAX_WATERING_TIME)
            duration = MAX_WATERING_TIME
        await self.coordinator.api.start_zone(
            self.zone, custom_run_duration=int(duration.total_seconds())
        )

    async def suspend(self, until: datetime) -> None:
        """Suspend automatic watering in the irrigation zone."""
        await self.coordinator.api.suspend_zone(self.zone, until=until)

    async def resume(self) -> None:
        """Resume automatic watering in the irrigation zone."""
        await self.coordinator.api.resume_zone(self.zone)
