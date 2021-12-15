"""Platform for Mazda sensor integration."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_PSI,
)

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaFuelRemainingSensor(client, coordinator, index))
        entities.append(MazdaFuelDistanceSensor(client, coordinator, index))
        entities.append(MazdaOdometerSensor(client, coordinator, index))
        entities.append(MazdaFrontLeftTirePressureSensor(client, coordinator, index))
        entities.append(MazdaFrontRightTirePressureSensor(client, coordinator, index))
        entities.append(MazdaRearLeftTirePressureSensor(client, coordinator, index))
        entities.append(MazdaRearRightTirePressureSensor(client, coordinator, index))

    async_add_entities(entities)


class MazdaFuelRemainingSensor(MazdaEntity, SensorEntity):
    """Class for the fuel remaining sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Fuel Remaining Percentage"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_fuel_remaining_percentage"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:gas-station"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.data["status"]["fuelRemainingPercent"]


class MazdaFuelDistanceSensor(MazdaEntity, SensorEntity):
    """Class for the fuel distance sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Fuel Distance Remaining"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_fuel_distance_remaining"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:gas-station"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        fuel_distance_km = self.data["status"]["fuelDistanceRemainingKm"]
        return (
            None
            if fuel_distance_km is None
            else round(
                self.hass.config.units.length(fuel_distance_km, LENGTH_KILOMETERS)
            )
        )


class MazdaOdometerSensor(MazdaEntity, SensorEntity):
    """Class for the odometer sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Odometer"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_odometer"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:speedometer"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        odometer_km = self.data["status"]["odometerKm"]
        return (
            None
            if odometer_km is None
            else round(self.hass.config.units.length(odometer_km, LENGTH_KILOMETERS))
        )


class MazdaFrontLeftTirePressureSensor(MazdaEntity, SensorEntity):
    """Class for the front left tire pressure sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Front Left Tire Pressure"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_front_left_tire_pressure"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        tire_pressure = self.data["status"]["tirePressure"]["frontLeftTirePressurePsi"]
        return None if tire_pressure is None else round(tire_pressure)


class MazdaFrontRightTirePressureSensor(MazdaEntity, SensorEntity):
    """Class for the front right tire pressure sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Front Right Tire Pressure"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_front_right_tire_pressure"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        tire_pressure = self.data["status"]["tirePressure"]["frontRightTirePressurePsi"]
        return None if tire_pressure is None else round(tire_pressure)


class MazdaRearLeftTirePressureSensor(MazdaEntity, SensorEntity):
    """Class for the rear left tire pressure sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Rear Left Tire Pressure"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_rear_left_tire_pressure"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        tire_pressure = self.data["status"]["tirePressure"]["rearLeftTirePressurePsi"]
        return None if tire_pressure is None else round(tire_pressure)


class MazdaRearRightTirePressureSensor(MazdaEntity, SensorEntity):
    """Class for the rear right tire pressure sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Rear Right Tire Pressure"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return f"{self.vin}_rear_right_tire_pressure"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        tire_pressure = self.data["status"]["tirePressure"]["rearRightTirePressurePsi"]
        return None if tire_pressure is None else round(tire_pressure)
