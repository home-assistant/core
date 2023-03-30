"""Platform for binary sensor integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .binary_sensor_description import (
    BINARY_SENSOR_TYPES_BASE,
    BINARY_SENSOR_TYPES_OVEN,
    BINARY_SENSOR_TYPES_SOLAR,
    BINARY_SENSOR_TYPES_SOLAR_EAST_WEST,
    BINARY_SENSOR_TYPES_WARMWATER,
    SolvisMaxBinarySensorEntityDescription,
)
from .const import (
    CONF_OPTION_OVEN,
    CONF_OPTION_SOLAR,
    CONF_OPTION_SOLAR_EAST_WEST,
    CONF_OPTION_WARMWATER_STATION,
    DOMAIN,
)
from .coordinator import SolvisRemoteCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add binary sensor entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SolvisMaxBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES_BASE
    )
    if entry.data.get(CONF_OPTION_WARMWATER_STATION):
        async_add_entities(
            SolvisMaxBinarySensor(coordinator, description)
            for description in BINARY_SENSOR_TYPES_WARMWATER
        )
    if entry.data.get(CONF_OPTION_SOLAR):
        async_add_entities(
            [SolvisMaxBinarySensor(coordinator, BINARY_SENSOR_TYPES_SOLAR)]
        )
    if entry.data.get(CONF_OPTION_SOLAR_EAST_WEST):
        async_add_entities(
            SolvisMaxBinarySensor(coordinator, description)
            for description in BINARY_SENSOR_TYPES_SOLAR_EAST_WEST
        )
    if entry.data.get(CONF_OPTION_OVEN):
        async_add_entities(
            [SolvisMaxBinarySensor(coordinator, BINARY_SENSOR_TYPES_OVEN)]
        )


class SolvisMaxBinarySensor(
    CoordinatorEntity[SolvisRemoteCoordinator], BinarySensorEntity
):
    """Representation of a Sensor."""

    entity_description: SolvisMaxBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SolvisRemoteCoordinator,
        description: SolvisMaxBinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.unique_id)},
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
            name=coordinator.name,
            configuration_url=coordinator.target_url,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the native sensor value."""

        if self.entity_description.key in self.coordinator.data.data:
            the_data_point = self.coordinator.data.data[self.entity_description.key]

            if the_data_point is None:
                return None
            if the_data_point["Key"] == "NA":
                return None

            the_value = the_data_point["Value"]
            return the_value

        return None
