"""Support for Hyyp binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import HyypDataUpdateCoordinator
from .entity import HyypSiteEntity

PARALLEL_UPDATES = 1

BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "isMaster": BinarySensorEntityDescription(key="isMaster"),
    "hasPin": BinarySensorEntityDescription(key="hasPin"),
    "isOnline": BinarySensorEntityDescription(key="isOnline"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up IDS Hyyp binary sensors based on a config entry."""
    coordinator: HyypDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        [
            HyypSensor(coordinator, site_id, sensor)
            for site_id in coordinator.data
            for sensor, value in coordinator.data[site_id].items()
            if sensor in BINARY_SENSOR_TYPES
            if value is not None
        ]
    )


class HyypSensor(HyypSiteEntity, BinarySensorEntity):
    """Representation of a IDS Hyyp sensor."""

    coordinator: HyypDataUpdateCoordinator

    def __init__(
        self,
        coordinator: HyypDataUpdateCoordinator,
        site_id: int,
        binary_sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, site_id)
        self._sensor_name = binary_sensor
        self._attr_name = f"{self.data['name']} {binary_sensor.title()}"
        self._attr_unique_id = f"{self._site_id}_{binary_sensor}"
        self.entity_description = BINARY_SENSOR_TYPES[binary_sensor]

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return bool(self.data[self._sensor_name])
