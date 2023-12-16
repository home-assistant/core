"""Support for Hydrawise sprinkler binary sensors."""

from __future__ import annotations

from pydrawise.schema import Sensor, Zone
import voluptuous as vol

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

CONTROLLER_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)

RAIN_SENSOR_BINARY_SENSOR: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="rain_sensor",
        translation_key="rain_sensor",
        icon="mdi:weather-pouring",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)

ZONE_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_watering",
        translation_key="watering",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)

BINARY_SENSOR_KEYS: list[str] = [
    desc.key
    for desc in (
        *CONTROLLER_BINARY_SENSORS,
        *RAIN_SENSOR_BINARY_SENSOR,
        *ZONE_BINARY_SENSORS,
    )
]


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
                sensor=sensor,
            )
            for sensor in controller.sensors
            for description in RAIN_SENSOR_BINARY_SENSOR
            if "rain sensor" in sensor.model.name.lower()
        )
        entities.extend(
            HydrawiseBinarySensor(coordinator, description, controller, zone=zone)
            for zone in controller.zones
            for description in ZONE_BINARY_SENSORS
        )
    async_add_entities(entities)


class HydrawiseBinarySensor(HydrawiseEntity, BinarySensorEntity):
    """A sensor implementation for Hydrawise device."""

    def _update_attrs(self) -> None:
        """Update state attributes."""
        if self.entity_description.key == "status":
            self._attr_is_on = self.coordinator.last_update_success
        elif self.entity_description.key == "is_watering":
            assert self.zone is not None
            self._attr_is_on = self.zone.scheduled_runs.current_run is not None
        elif self.entity_description.key == "rain_sensor":
            assert self.sensor is not None
            self._attr_is_on = self.sensor.status.active
