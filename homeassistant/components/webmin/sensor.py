"""Support for Webmin sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WebminUpdateCoordinator

SENSOR_TYPES = [
    SensorEntityDescription(
        key="load_1m",
        name="Load (1m)",
        icon="mdi:cpu-64-bit",
        state_class=SensorStateClass.MEASUREMENT,
    )
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Webmin sensors based on a config entry."""
    async_add_entities(
        [
            WebminSensor(hass.data[DOMAIN][entry.entry_id], description)
            for description in SENSOR_TYPES
        ]
    )


class WebminSensor(CoordinatorEntity[WebminUpdateCoordinator], SensorEntity):
    """Represents a Webmin sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self, coordinator: WebminUpdateCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Webmin sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"

    def _handle_coordinator_update(self) -> None:
        if self.entity_description.key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[self.entity_description.key]
        self.async_write_ha_state()
