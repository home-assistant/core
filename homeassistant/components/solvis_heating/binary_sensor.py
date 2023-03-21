"""Platform for binary sensor integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .binary_sensor_description import (
    BINARY_SENSOR_TYPES,
    SolvisMaxBinarySensorEntityDescription,
)
from .const import DOMAIN
from .solvis_remote_data import SolvisRemoteData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add SolvisMax entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolvisMaxBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    )


class SolvisMaxBinarySensor(CoordinatorEntity[SolvisRemoteData], BinarySensorEntity):
    """Representation of a Sensor."""

    entity_description: SolvisMaxBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SolvisRemoteData,
        description: SolvisMaxBinarySensorEntityDescription,
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
    def is_on(self) -> bool:
        """Return the native sensor value."""

        raw_attr = self.coordinator.data.data[self.entity_description.key]

        if raw_attr is None:
            return False

        the_value = raw_attr["Value"]
        # if self.entity_description.value:
        #    converted_val = self.entity_description.value(the_value)
        #    return converted_val

        return the_value
