"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .sensor_description import SENSOR_TYPES, SolvisMaxSensorEntityDescription
from .solvis_remote_data import SolvisRemoteData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add SolvisMax entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolvisMaxSensor(coordinator, description) for description in SENSOR_TYPES
    )


class SolvisMaxSensor(CoordinatorEntity[SolvisRemoteData], SensorEntity):
    """Representation of a Sensor."""

    entity_description: SolvisMaxSensorEntityDescription

    def __init__(
        self,
        coordinator: SolvisRemoteData,
        description: SolvisMaxSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer="Solvis",
            name=coordinator.name,
            configuration_url=coordinator.host,
        )

    @property
    def native_value(self) -> Any | None:
        """Return the native sensor value."""

        raw_attr = self.coordinator.data.data[self.entity_description.key]

        if raw_attr is None:
            return None

        the_value = raw_attr["Value"]
        if self.entity_description.value:
            converted_val = self.entity_description.value(the_value)
            return converted_val

        return the_value
