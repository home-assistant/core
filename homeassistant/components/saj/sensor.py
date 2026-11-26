"""SAJ solar inverter interface."""

from typing import override

import aiosaj

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SAJConfigEntry, SAJDataUpdateCoordinator

SAJ_UNIT_MAPPINGS = {
    "": None,
    "h": UnitOfTime.HOURS,
    "kg": UnitOfMass.KILOGRAMS,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "W": UnitOfPower.WATT,
    "°C": UnitOfTemperature.CELSIUS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SAJConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SAJ sensors from a config entry."""
    coordinator = entry.runtime_data

    # aiosaj also reports voltage, current and frequency channels, which have
    # no unit mapping and therefore no entities yet.
    async_add_entities(
        SAJsensor(coordinator, entry.unique_id, sensor)
        for sensor in coordinator.sensor_def
        if sensor.enabled and sensor.unit in SAJ_UNIT_MAPPINGS
    )


class SAJsensor(CoordinatorEntity[SAJDataUpdateCoordinator], SensorEntity):
    """Representation of a SAJ sensor."""

    def __init__(
        self,
        coordinator: SAJDataUpdateCoordinator,
        serialnumber: str | None,
        saj_sensor: aiosaj.Sensor,
    ) -> None:
        """Initialize the SAJ sensor."""
        super().__init__(coordinator)
        self._sensor = saj_sensor

        if saj_sensor.name in ("current_power", "temperature"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if saj_sensor.name == "total_yield":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._attr_unique_id = f"{serialnumber}_{saj_sensor.name}"
        native_uom = SAJ_UNIT_MAPPINGS[saj_sensor.unit]
        self._attr_native_unit_of_measurement = native_uom
        self._attr_name = f"saj_{saj_sensor.name}"
        if native_uom == UnitOfPower.WATT:
            self._attr_device_class = SensorDeviceClass.POWER
        if native_uom == UnitOfEnergy.KILO_WATT_HOUR:
            self._attr_device_class = SensorDeviceClass.ENERGY
        if native_uom in (
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._sensor.value
