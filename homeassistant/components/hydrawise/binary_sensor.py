"""Support for Hydrawise sprinkler binary sensors."""

from __future__ import annotations

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

BINARY_SENSOR_STATUS = BinarySensorEntityDescription(
    key="status",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
)

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="is_watering",
        translation_key="watering",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
)

BINARY_SENSOR_KEYS: list[str] = [
    desc.key for desc in (BINARY_SENSOR_STATUS, *BINARY_SENSOR_TYPES)
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
    entities = []
    for controller in coordinator.data.controllers.values():
        entities.append(
            HydrawiseBinarySensor(coordinator, BINARY_SENSOR_STATUS, controller)
        )
        entities.extend(
            HydrawiseBinarySensor(coordinator, description, controller, zone)
            for zone in controller.zones
            for description in BINARY_SENSOR_TYPES
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
