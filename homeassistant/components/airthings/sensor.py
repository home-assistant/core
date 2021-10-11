"""Support for Airthings sensors."""
from __future__ import annotations

from airthings import AirthingsDevice

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PM1,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_MBAR,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

SENSORS: dict[str, SensorEntityDescription] = {
    "radonShortTermAvg": SensorEntityDescription(
        key="radonShortTermAvg",
        native_unit_of_measurement="Bq/m³",
        name="Radon",
    ),
    "temp": SensorEntityDescription(
        key="temp",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        name="Temperature",
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        name="Humidity",
    ),
    "pressure": SensorEntityDescription(
        key="pressure",
        device_class=DEVICE_CLASS_PRESSURE,
        native_unit_of_measurement=PRESSURE_MBAR,
        name="Pressure",
    ),
    "battery": SensorEntityDescription(
        key="battery",
        device_class=DEVICE_CLASS_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        name="Battery",
    ),
    "co2": SensorEntityDescription(
        key="co2",
        device_class=DEVICE_CLASS_CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        name="CO2",
    ),
    "voc": SensorEntityDescription(
        key="voc",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        name="VOC",
    ),
    "light": SensorEntityDescription(
        key="light",
        native_unit_of_measurement=PERCENTAGE,
        name="Light",
    ),
    "virusRisk": SensorEntityDescription(
        key="virusRisk",
        name="Virus Risk",
    ),
    "mold": SensorEntityDescription(
        key="mold",
        name="Mold",
    ),
    "rssi": SensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        name="RSSI",
        entity_registry_enabled_default=False,
    ),
    "pm1": SensorEntityDescription(
        key="pm1",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=DEVICE_CLASS_PM1,
        name="PM1",
    ),
    "pm25": SensorEntityDescription(
        key="pm25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=DEVICE_CLASS_PM25,
        name="PM25",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airthings sensor."""

    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        AirthingsHeaterEnergySensor(
            coordinator,
            airthings_device,
            SENSORS[sensor_types],
        )
        for airthings_device in coordinator.data.values()
        for sensor_types in airthings_device.sensor_types
        if sensor_types in SENSORS
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

        self._attr_name = f"{airthings_device.name} {entity_description.name}"
        self._attr_unique_id = f"{airthings_device.device_id}_{entity_description.key}"
        self._id = airthings_device.device_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, airthings_device.device_id)},
            "name": airthings_device.name,
            "manufacturer": "Airthings",
        }

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self._id].sensors[self.entity_description.key]
