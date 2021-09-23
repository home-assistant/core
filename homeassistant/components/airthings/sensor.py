"""Support for Airthings sensors."""
from __future__ import annotations

from airthings import AirthingsDevice

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    PERCENTAGE,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

SENSORS: dict[str, SensorEntityDescription] = {
    "radonShortTermAvg": SensorEntityDescription(
        key="radonShortTermAvg",
        native_unit_of_measurement="Bq/m³",
    ),
    "temp": SensorEntityDescription(
        key="temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        device_class=DEVICE_CLASS_PRESSURE,
        native_unit_of_measurement=PRESSURE_MBAR,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        device_class=DEVICE_CLASS_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    "co2": SensorEntityDescription(
        key="co2",
        device_class=DEVICE_CLASS_CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    "voc": SensorEntityDescription(
        key="voc",
        device_class=DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Airthings sensor."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AirthingsHeaterEnergySensor(
            coordinator,
            airthings_device,
            SENSORS[sensor_type],
        )
        for airthings_device in coordinator.data.values()
        for sensor_type in airthings_device.sensor_types
        if sensor_type in SENSORS
    ]
    async_add_entities(entities)


class AirthingsHeaterEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Airthings Sensor device."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        airthings_device: AirthingsDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_name = f"{airthings_device.name} {entity_description.key}"
        self._attr_unique_id = f"{airthings_device.device_id}_{entity_description.key}"
        self._id = airthings_device.device_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, airthings_device.device_id)},
            "name": self.name,
            "manufacturer": "Airthings",
        }

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self._id].sensors[self.entity_description.key]
