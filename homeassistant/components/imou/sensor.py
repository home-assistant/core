"""Support for Imou sensor entities."""

from typing import override

from pyimouapi.const import PARAM_STATE_VARIANT, STATE_VARIANT_NUMERIC
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import PARAM_STATE, PARAM_STATUS, imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 0

SENSOR_TYPES = (
    PARAM_STATUS,
    "battery",
    "storage_used",
    "temperature_current",
    "humidity_current",
    "power",
    "voltage",
    "current",
    "switch_cnt",
    "use_electricity",
    "use_time",
)

STATUS_OPTIONS = ["online", "offline", "sleep", "upgrading"]

SENSOR_UNITS: dict[str, str] = {
    "battery": PERCENTAGE,
    "temperature_current": UnitOfTemperature.CELSIUS,
    "humidity_current": PERCENTAGE,
    "power": UnitOfPower.WATT,
    "voltage": UnitOfElectricPotential.VOLT,
    "current": UnitOfElectricCurrent.AMPERE,
    "use_electricity": UnitOfEnergy.KILO_WATT_HOUR,
    "use_time": UnitOfTime.MINUTES,
    "storage_used": PERCENTAGE,
}

SENSOR_DEVICE_CLASS: dict[str, SensorDeviceClass] = {
    "battery": SensorDeviceClass.BATTERY,
    "temperature_current": SensorDeviceClass.TEMPERATURE,
    "humidity_current": SensorDeviceClass.HUMIDITY,
    "power": SensorDeviceClass.POWER,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "use_electricity": SensorDeviceClass.ENERGY,
    "use_time": SensorDeviceClass.DURATION,
    PARAM_STATUS: SensorDeviceClass.ENUM,
}

SENSOR_STATE_CLASS: dict[str, SensorStateClass] = {
    "battery": SensorStateClass.MEASUREMENT,
    "temperature_current": SensorStateClass.MEASUREMENT,
    "humidity_current": SensorStateClass.MEASUREMENT,
    "power": SensorStateClass.MEASUREMENT,
    "voltage": SensorStateClass.MEASUREMENT,
    "current": SensorStateClass.MEASUREMENT,
    "use_electricity": SensorStateClass.TOTAL_INCREASING,
    "use_time": SensorStateClass.TOTAL_INCREASING,
    "switch_cnt": SensorStateClass.TOTAL,
    "storage_used": SensorStateClass.MEASUREMENT,
}

SENSOR_ENTITY_CATEGORY: dict[str, EntityCategory] = {
    "battery": EntityCategory.DIAGNOSTIC,
    "storage_used": EntityCategory.DIAGNOSTIC,
    PARAM_STATUS: EntityCategory.DIAGNOSTIC,
}

SENSOR_DISPLAY_PRECISION: dict[str, int] = {
    "battery": 0,
    "temperature_current": 1,
    "humidity_current": 1,
    "storage_used": 0,
}


def _iter_sensors(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[str, ImouHaDevice]]:
    """Return (sensor_type, device) pairs for supported sensors."""
    return [
        (sensor_type, device)
        for device in coordinator.devices
        for sensor_type in device.sensors
        if sensor_type in SENSOR_TYPES
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou sensor entities."""
    coordinator = entry.runtime_data

    def _add_sensors(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouSensor(coordinator, sensor_type, device)
            for sensor_type, device in _iter_sensors(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    coordinator.new_device_callbacks.append(_add_sensors)

    @callback
    def _remove_new_device_callback() -> None:
        if _add_sensors in coordinator.new_device_callbacks:
            coordinator.new_device_callbacks.remove(_add_sensors)

    entry.async_on_unload(_remove_new_device_callback)
    _add_sensors(coordinator.devices)


class ImouSensor(ImouEntity, SensorEntity):
    """Imou sensor entity."""

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        entity_type: str,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou sensor entity."""
        super().__init__(coordinator, entity_type, device)
        if device_class := SENSOR_DEVICE_CLASS.get(entity_type):
            self._attr_device_class = device_class
        if entity_category := SENSOR_ENTITY_CATEGORY.get(entity_type):
            self._attr_entity_category = entity_category
        if entity_type == PARAM_STATUS:
            self._attr_options = STATUS_OPTIONS

    @property
    def _is_numeric_variant(self) -> bool:
        """Return True when the sensor value is numeric."""
        return (
            self.device.sensors[self._entity_type].get(PARAM_STATE_VARIANT)
            == STATE_VARIANT_NUMERIC
        )

    @property
    @override
    def state_class(self) -> SensorStateClass | None:
        """Return state class for numeric sensor values."""
        if not self._is_numeric_variant:
            return None
        return SENSOR_STATE_CLASS.get(self._entity_type)

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.device.sensors[self._entity_type][PARAM_STATE]

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit when the sensor value is numeric."""
        if not self._is_numeric_variant:
            return None
        return SENSOR_UNITS.get(self._entity_type)

    @property
    @override
    def suggested_display_precision(self) -> int | None:
        """Return display precision for numeric sensor values."""
        if not self._is_numeric_variant:
            return None
        return SENSOR_DISPLAY_PRECISION.get(self._entity_type)
