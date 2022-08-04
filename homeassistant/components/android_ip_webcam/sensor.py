"""Support for Android IP Webcam sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import StateType

from . import AndroidIPCamBaseEntity, AndroidIPCamDataUpdateCoordinator
from .const import DOMAIN, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IP Webcam sensors from config entry."""

    coordinator: AndroidIPCamDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    sensor_types = [
        sensor
        for sensor in SENSOR_TYPES
        if sensor.key
        in coordinator.ipcam.enabled_sensors
        + ["audio_connections", "video_connections"]
    ]
    async_add_entities(
        [IPWebcamSensor(coordinator, description) for description in sensor_types]
    )


class IPWebcamSensor(AndroidIPCamBaseEntity, SensorEntity):
    """Representation of a IP Webcam sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = None
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return sensor native value."""
        if self.entity_description.key in ("audio_connections", "video_connections"):
            return self._ipcam.status_data.get(self.entity_description.key)

        value, _ = self._ipcam.export_sensor(self.entity_description.key)
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return sensor native unit of measurement."""
        _, unit = self._ipcam.export_sensor(self.entity_description.key)
        return unit

    @property
    def icon(self) -> str | None:
        """Return the icon for the sensor."""
        if self.entity_description.key == "battery_level":
            battery_level = (
                int(self.native_value)
                if self.native_value is not None
                else self.native_value
            )
            return icon_for_battery_level(battery_level)
        return self.entity_description.icon
