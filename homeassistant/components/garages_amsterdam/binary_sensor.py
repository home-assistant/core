"""Binary Sensor platform for Garages Amsterdam."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GaragesAmsterdamDataUpdateCoordinator
from .entity import GaragesAmsterdamEntity

BINARY_SENSORS = {
    "state",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator: GaragesAmsterdamDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]

    async_add_entities(
        GaragesAmsterdamBinarySensor(coordinator, entry.data["garage_name"], info_type)
        for info_type in BINARY_SENSORS
    )


class GaragesAmsterdamBinarySensor(GaragesAmsterdamEntity, BinarySensorEntity):
    """Binary Sensor representing garages amsterdam data."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = None

    @property
    def is_on(self) -> bool:
        """If the binary sensor is currently on or off."""
        return (
            getattr(self.coordinator.data[self._garage_name], self._info_type) != "ok"
        )
