"""Support for Oncue sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

STATIC_SENSORS = {"GensetSerialNumber", "GensetModelNumberSelect"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[OncueSensor] = []
    for device_id, device in coordinator.data.items():
        entities.extend(
            OncueSensor(
                coordinator,
                device_id,
                name,
            )
            for name in device["sensors"]
            if name not in STATIC_SENSORS
        )

    async_add_entities(entities)


class OncueSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Oncue sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, device_id: str, name: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._sensor_name = name
        device_data = coordinator.data[device_id]
        sensor_data = device_data["sensors"]
        sensor_data = sensor_data[self._sensor_name]
        value = sensor_data["value"]
        if isinstance(value, str) and len(sensor_data["displayvalue"]) > len(value) + 1:
            self._attr_native_unit_of_measurement = sensor_data["displayvalue"][
                len(value) + 1
            ]
        self._attr_unique_id = f"{device_id}_{name}"
        self._attr_name = f'{device_data["name"]} {sensor_data["displayname"]}'
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_data["name"],
            sw_version=device_data["version"],
            model=device_data["product_name"],
            manufacturer="Kohler",
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        sensor_data = self.coordinator.data[self._device_id]["sensors"][
            self._sensor_name
        ]
        return sensor_data["value"]
