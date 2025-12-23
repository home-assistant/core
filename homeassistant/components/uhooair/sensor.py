"""imports for sensor.py file."""

from uhooapi import Device

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UhooDataUpdateCoordinator
from .const import (
    API_TEMP,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SENSOR_TYPES,
    UnitOfTemperature,
)

PARALLEL_UPDATES = True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    sensors = [
        UhooSensorEntity(description, serial_number, coordinator)
        for serial_number in coordinator.data
        for description in SENSOR_TYPES
    ]

    async_add_entities(sensors, False)


class UhooSensorEntity(CoordinatorEntity, SensorEntity):
    """Uhoo Sensor Object with init and methods."""

    def __init__(
        self,
        description: SensorEntityDescription,
        serial_number: str,
        coordinator: UhooDataUpdateCoordinator,
    ) -> None:
        """Initialize Uhoo Sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self.entity_description = description
        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo."""
        device: Device = self.coordinator.data[self._serial_number]
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=device.device_name,
            model=MODEL,
            manufacturer=MANUFACTURER,
        )

    @property
    def native_value(self) -> StateType:
        """State of the sensor."""
        device: Device = self.coordinator.data[self._serial_number]
        state = getattr(device, self.entity_description.key)
        if isinstance(state, list):
            state = state[0]
        return state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        # Handle temperature unit conversion
        if self.entity_description.key == API_TEMP:
            if self._coordinator.user_settings_temp == "f":
                return UnitOfTemperature.FAHRENHEIT
            return UnitOfTemperature.CELSIUS

        # For all other sensors, use the unit from entity_description
        return self.entity_description.native_unit_of_measurement
