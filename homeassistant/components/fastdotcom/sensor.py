"""Sensor platform for the Fast.com integration."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FastdotcomConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fast.com sensors from a config entry."""
    async_add_entities(
        [
            DownloadSpeedSensor(entry.entry_id, entry.runtime_data),
            UploadSpeedSensor(entry.entry_id, entry.runtime_data),
            UnloadedPingSensor(entry.entry_id, entry.runtime_data),
            LoadedPingSensor(entry.entry_id, entry.runtime_data),
        ]
    )


class DownloadSpeedSensor(
    CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity
):
    """Representation of the download speed sensor."""

    _attr_name = "Download speed"
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_download_speed"

    @property
    def native_value(self) -> float:
        """Return the sensor's current value."""
        value = self.coordinator.data.get("download_speed", 0.00)
        return round(float(value), 2)


class UploadSpeedSensor(DownloadSpeedSensor):
    """Representation of the upload speed sensor."""

    _attr_name = "Upload speed"
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_upload"

    @property
    def native_value(self) -> float:
        """Return the sensor's current value."""
        value = self.coordinator.data.get("upload_speed", 0.00)
        return round(float(value), 2)


class UnloadedPingSensor(SensorEntity):
    """Representation of the unloaded ping sensor."""

    _attr_name = "Unloaded ping"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_unloaded_ping"

    @property
    def native_value(self) -> float:
        """Return the sensor's current value."""
        value = self.coordinator.data.get("ping_unloaded", 0.00)
        return round(float(value), 2)


class LoadedPingSensor(SensorEntity):
    """Representation of the loaded ping sensor."""

    _attr_name = "Loaded ping"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_loaded_ping"

    @property
    def native_value(self) -> float:
        """Return the sensor's current value."""
        value = self.coordinator.data.get("ping_loaded", 0.00)
        return round(float(value), 2)
