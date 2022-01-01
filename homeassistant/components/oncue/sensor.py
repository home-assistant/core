"""Support for Oncue sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OnCueDataUpdateCoordinator
from .const import DOMAIN

STATIC_SENSORS = {"GensetSerialNumber", "GensetModelNumberSelect"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: OnCueDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[OncueSensor] = []
    for device_id, device in coordinator.data.items():
        entities.extend(
            OncueSensor(
                coordinator,
                device_id,
                name,
            )
            for name in device["sensors"]
            if name in STATIC_SENSORS
        )

    async_add_entities(entities)


class OncueSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Oncue sensor."""

    coordinator: OnCueDataUpdateCoordinator

    def __init__(
        self, coordinator: OnCueDataUpdateCoordinator, device_id: str, name: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._sensor_name = name
        device_data = coordinator.data[device_id]
        sensor_data = device_data["sensors"]
        device_name = device_data["display_name"]
        sensor_data = sensor_data[self._sensor_name]
        sensor_display_name = sensor_data["displayname"]
        unit = None
        value = sensor_data["value"]
        if len(sensor_data["displayvalue"]) > len(value) + 1:
            unit = sensor_data["displayvalue"][len(value) + 1]
        self._attr_unique_id = f"{device_id}_{name}"
        self._attr_name = f"{device_name} {sensor_display_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            sw_version=device_data["version"],
            model=sensor_data["GensetModelNumberSelect"]["displayvalue"],
            manufacturer="Kohler",
        )
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        sensor_data = self.coordinator.data[self._device_id]["sensors"][
            self._sensor_name
        ]
        return sensor_data["value"]
