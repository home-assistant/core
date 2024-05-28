"""Support for Hydrawise sprinkler binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HydrawiseDataUpdateCoordinator
from .entity import HydrawiseEntity


@dataclass(frozen=True, kw_only=True)
class HydrawiseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Hydrawise binary sensor."""

    value_fn: Callable[[HydrawiseBinarySensor], bool | None]


CONTROLLER_BINARY_SENSORS: tuple[HydrawiseBinarySensorEntityDescription, ...] = (
    HydrawiseBinarySensorEntityDescription(
        key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda status_sensor: status_sensor.coordinator.last_update_success,
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
            HydrawiseBinarySensor(coordinator, description, controller, zone_id=zone.id)
            for zone in controller.zones
            for description in ZONE_BINARY_SENSORS
        )
    async_add_entities(entities)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    entity_description: HydrawiseBinarySensorEntityDescription

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_is_on = self.entity_description.value_fn(self)
