"""Support for the linknlink binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LinknLinkCoordinator
from .entity import LinknLinkEntity

BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="pir_detected",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    BinarySensorEntityDescription(
        key="doorsensor_status",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the linknlink binary sensor."""

    coordinator: LinknLinkCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        LinknLinkBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
        if description.key in coordinator.data
    )


class LinknLinkBinarySensor(LinknLinkEntity, BinarySensorEntity):
    """Representation of a linknlink binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        if description.key in self.coordinator.data:
            self.entity_description = description
            self._attr_is_on = bool(self.coordinator.data[description.key])
            self._attr_unique_id = f"{coordinator.api.mac.hex()}-{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update."""
        self._update_attr()
        super()._handle_coordinator_update()

    @callback
    def _update_attr(self) -> None:
        """Update attributes for sensor."""
        self._attr_is_on = bool(self.coordinator.data[self.entity_description.key])
