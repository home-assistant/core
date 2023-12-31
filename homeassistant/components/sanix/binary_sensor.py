"""Platform for Binary Sensor integration."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_API_STATUS, DOMAIN, MANUFACTURER
from .coordinator import SanixCoordinator


@dataclass(frozen=True)
class SanixBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Sanix Binary Sensor entities."""

    attr: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}


BINARY_SENSOR_TYPES: tuple[SanixBinarySensorEntityDescription, ...] = (
    SanixBinarySensorEntityDescription(
        key=ATTR_API_STATUS,
        translation_key="status",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sanix Binary Sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for description in BINARY_SENSOR_TYPES:
        if coordinator.data.get(description.key):
            sensors.append(
                SanixBinarySensor(
                    coordinator, entry.title, str(entry.unique_id), description
                )
            )

    async_add_entities(sensors, False)


class SanixBinarySensor(CoordinatorEntity[SanixCoordinator], BinarySensorEntity):
    """Sanix Binary Sensor entity."""

    _attr_has_entity_name = True
    entity_description: SanixBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SanixCoordinator,
        name: str,
        serial_no: str,
        description: SanixBinarySensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{name}-{description.key}".lower()
        self._attr_is_on = coordinator.data[description.key] == 1
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, name)},
            manufacturer=MANUFACTURER,
            name=name,
            serial_number=serial_no,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.entity_description.key] == 1
        self.async_write_ha_state()
