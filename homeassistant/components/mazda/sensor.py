"""Platform for Mazda sensor integration."""
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_PSI,
)

from . import MazdaEntity
from .const import DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaFuelRemainingSensor(coordinator, index))
        entities.append(MazdaFuelDistanceSensor(coordinator, index))
        entities.append(MazdaOdometerSensor(coordinator, index))
        entities.append(MazdaFrontLeftTirePressureSensor(coordinator, index))
        entities.append(MazdaFrontRightTirePressureSensor(coordinator, index))
        entities.append(MazdaRearLeftTirePressureSensor(coordinator, index))
        entities.append(MazdaRearRightTirePressureSensor(coordinator, index))

    async_add_entities(entities)


class MazdaFuelRemainingSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:gas-station"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.index]["status"]["fuelRemainingPercent"]


class MazdaFuelDistanceSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:gas-station"

    @property
    def state(self):
        """Return the state of the sensor."""
        fuel_distance_km = self.coordinator.data[self.index]["status"][
            "fuelDistanceRemainingKm"
        ]
        return round(self.hass.config.units.length(fuel_distance_km, LENGTH_KILOMETERS))


class MazdaOdometerSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:speedometer"

    @property
    def state(self):
        """Return the state of the sensor."""
        odometer_km = self.coordinator.data[self.index]["status"]["odometerKm"]
        return round(self.hass.config.units.length(odometer_km, LENGTH_KILOMETERS))


class MazdaFrontLeftTirePressureSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(
            self.coordinator.data[self.index]["status"]["tirePressure"][
                "frontLeftTirePressurePsi"
            ]
        )


class MazdaFrontRightTirePressureSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(
            self.coordinator.data[self.index]["status"]["tirePressure"][
                "frontRightTirePressurePsi"
            ]
        )


class MazdaRearLeftTirePressureSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(
            self.coordinator.data[self.index]["status"]["tirePressure"][
                "rearLeftTirePressurePsi"
            ]
        )


class MazdaRearRightTirePressureSensor(MazdaEntity):
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
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PRESSURE_PSI

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:car-tire-alert"

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(
            self.coordinator.data[self.index]["status"]["tirePressure"][
                "rearRightTirePressurePsi"
            ]
        )
