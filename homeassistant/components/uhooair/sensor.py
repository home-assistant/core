"""imports for sensor.py file."""

from uhooapi import Device

from homeassistant import core
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UhooDataUpdateCoordinator
from .const import (
    API_TEMP,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_LABEL,
    ATTR_UNIQUE_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SENSOR_TYPES,
    UnitOfTemperature,
)

PARALLEL_UPDATES = True


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    sensors = [
        UhooSensorEntity(sensor, serial_number, coordinator)
        for serial_number in coordinator.data
        for sensor in SENSOR_TYPES
    ]

    async_add_entities(sensors, False)


class UhooSensorEntity(CoordinatorEntity, SensorEntity):
    """Uhoo Sensor Object with init and methods."""

    def __init__(
        self, kind: str, serial_number: str, coordinator: UhooDataUpdateCoordinator
    ) -> None:
        """Initialize Uhoo Sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._kind = kind
        self._serial_number = serial_number
        self._attr_device_class = SensorDeviceClass(
            SENSOR_TYPES[self._kind][ATTR_DEVICE_CLASS]
        )
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = SENSOR_TYPES[self._kind][ATTR_ICON]

    @property
    def name(self) -> str:
        """Return the name of the particular component."""
        device: Device = self.coordinator.data[self._serial_number]
        return f"{device.device_name} {SENSOR_TYPES[self._kind][ATTR_LABEL]}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""
        return f"{self._serial_number}_{SENSOR_TYPES[self._kind][ATTR_UNIQUE_ID]}"

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
        device: Device = self._coordinator.data[self._serial_number]
        state = getattr(device, self._kind)
        if isinstance(state, list):
            state = state[0]
        return state

    @property
    def state_class(self) -> str | None:
        """Return the state class of this entity, from STATE_CLASSES, if any."""
        return self._attr_state_class

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of this entity, from STATE_CLASSES, if any."""
        return self._attr_device_class

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._attr_icon

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement."""
        if self._kind == API_TEMP:
            if self._coordinator.user_settings_temp == "f":
                return str(UnitOfTemperature.FAHRENHEIT)
            return str(UnitOfTemperature.CELSIUS)
        return str(SENSOR_TYPES[self._kind][ATTR_UNIT_OF_MEASUREMENT])
