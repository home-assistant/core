import re

from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfDataRate
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FastdotcomConfigEntry, FastdotcomDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FastdotcomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fast.com sensors."""
    coordinator = entry.runtime_data
    unique_id = entry.entry_id
    async_add_entities([
        DownloadSpeedSensor(unique_id, coordinator),
        UploadSpeedSensor(unique_id, coordinator),
        UnloadedPingSensor(unique_id, coordinator),
        LoadedPingSensor(unique_id, coordinator),
    ])


class DownloadSpeedSensor(CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity):
    """Sensor for Fast.com download speed."""

    _attr_name = "Download Speed"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator) -> None:
        """Initialize the Download Speed sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_download"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.fast.com",
        )

    @property
    def native_value(self) -> float:
        """Return the download speed parsed from coordinator data."""
        if not self.coordinator.data:
        # Log a warning if you want to track this situation
            return 0.0
        for line in self.coordinator.data.splitlines():
            if "Download Speed:" in line:
                match = re.search(r"(\d+(?:\.\d+)?)", line)
                if match:
                    return float(match.group(1))
        return 0.0

class UploadSpeedSensor(CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity):
    """Sensor for Fast.com upload speed."""                                               
                                                                                            
    _attr_name = "Upload Speed"                                                           
    _attr_device_class = SensorDeviceClass.DATA_RATE                                        
    _attr_native_unit_of_measurement = UnitOfDataRate.MEGABITS_PER_SECOND                   
    _attr_state_class = SensorStateClass.MEASUREMENT                                        
    _attr_should_poll = False                                                               
    _attr_has_entity_name = True                                                            
                                                                                            
    def __init__(self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator) -> None:
        """Initialize the Upload Speed sensor."""                                         
        super().__init__(coordinator)                                                       
        self._attr_unique_id = f"{entry_id}_upload"                                       
        self._attr_device_info = DeviceInfo(                                                
            identifiers={(DOMAIN, entry_id)},                                               
            entry_type=DeviceEntryType.SERVICE,                                             
            configuration_url="https://www.fast.com",                                       
        )                                                                                   
                                                                                            
    @property                                        
    def native_value(self) -> float:                 
        """Return the upload speed parsed from coordinator data."""
        if not self.coordinator.data:                                
        # Log a warning if you want to track this situation          
            return 0.0                                               
        for line in self.coordinator.data.splitlines():              
            if "Upload Speed:" in line:                            
                match = re.search(r"(\d+(?:\.\d+)?)", line)          
                if match:                                            
                    return float(match.group(1))                     
        return 0.0 

class UnloadedPingSensor(CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity):
    """Sensor for Fast.com unloaded ping."""
    
    _attr_name = "Unloaded Ping"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_has_entity_name = True
    
    def __init__(self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator) -> None:
        """Initialize the Unloaded Ping sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_unloaded_ping"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.fast.com",
        )
    
    @property
    def native_value(self) -> float:
        """Return the unloaded ping parsed from coordinator data."""
        if not self.coordinator.data:
            # Optionally log a warning if data is missing
            return 0.0
        for line in self.coordinator.data.splitlines():
            if "Unloaded Ping:" in line:
                match = re.search(r"(\d+(?:\.\d+)?)", line)
                if match:
                    return float(match.group(1))
        return 0.0


class LoadedPingSensor(CoordinatorEntity[FastdotcomDataUpdateCoordinator], SensorEntity):
    """Sensor for Fast.com loaded ping."""
    
    _attr_name = "Loaded Ping"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_has_entity_name = True
    
    def __init__(self, entry_id: str, coordinator: FastdotcomDataUpdateCoordinator) -> None:
        """Initialize the Loaded Ping sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_loaded_ping"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.fast.com",
        )
    
    @property
    def native_value(self) -> float:
        """Return the loaded ping parsed from coordinator data."""
        if not self.coordinator.data:
            # Optionally log a warning if data is missing
            return 0.0
        for line in self.coordinator.data.splitlines():
            if "Loaded Ping:" in line:
                match = re.search(r"(\d+(?:\.\d+)?)", line)
                if match:
                    return float(match.group(1))
        return 0.0
