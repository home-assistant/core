from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
    UnitOfDataRate,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator


async def async_setup_entry(hass, entry: FastdotcomConfigEntry, async_add_entities):

    async_add_entities(
        [
            DownloadSpeedSensor(entry.entry_id, entry.runtime_data),
            UploadSpeedSensor(entry.entry_id, entry.runtime_data),
            UnloadedPingSensor(entry.entry_id, entry.runtime_data),
            LoadedPingSensor(entry.entry_id, entry.runtime_data),
        ]
    )


class DownloadSpeedSensor(CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity):
    _attr_name = "Download speed"
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry_id, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_download_speed"

    @property
    def native_value(self):
        return round(self.coordinator.data.get("download_speed", 0.00), 2)


class UploadSpeedSensor(DownloadSpeedSensor):
    _attr_name = "Upload speed"

    def __init__(self, entry_id, coordinator):
        super().__init__(entry_id, coordinator)
        self._attr_unique_id = f"{entry_id}_upload"

    @property
    def native_value(self):
        return round(self.coordinator.data.get("upload_speed", 0.00), 2)


class UnloadedPingSensor(SensorEntity):
    _attr_name = "Unloaded ping"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry_id, coordinator):
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_unloaded_ping"

    @property
    def native_value(self):
        return round(self.coordinator.data.get("ping_unloaded", 0), 1)


class LoadedPingSensor(SensorEntity):
    _attr_name = "Loaded ping"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry_id, coordinator):
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_loaded_ping"

    @property
    def native_value(self):
        return round(self.coordinator.data.get("ping_loaded", 0), 1)
