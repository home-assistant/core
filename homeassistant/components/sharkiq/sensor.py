# Shark IQ Battery Sensor.

from collections.abc import Iterable
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SHARK
from .coordinator import SharkIqConfigEntry, SharkIqUpdateCoordinator, SkegoxUpdateCoordinator, SharkDevice, get_device_model
from .sharkiq_pypi.sharkiq import Properties

# Set up the Shark IQ battery sensor.
async def async_setup_entry(hass: HomeAssistant, config_entry: SharkIqConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,) -> None:
    coordinator = config_entry.runtime_data
    devices: Iterable[SharkDevice] = coordinator.shark_vacs.values()
    async_add_entities([SharkBatterySensor(d, coordinator) for d in devices])

# Shark IQ battery sensor entity.
class SharkBatterySensor(CoordinatorEntity, SensorEntity):
    _coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True
    _attr_name = "Battery"

    # Create a new SharkBatterySensor.
    def __init__(self, sharkiq: SharkDevice, coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.sharkiq = sharkiq
        self._attr_unique_id = f"{sharkiq.serial_number}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
            manufacturer=SHARK,
            model=get_device_model(sharkiq),
            name=sharkiq.name,
            sw_version=sharkiq.get_property_value(Properties.ROBOT_FIRMWARE_VERSION),
        )

    # Determine if the sensor is available based on API results.
    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.device_is_online(
            self.sharkiq.serial_number
        )

    # Return the current battery level.
    @property
    def native_value(self) -> int | None:
        return self.sharkiq.get_property_value(Properties.BATTERY_CAPACITY)