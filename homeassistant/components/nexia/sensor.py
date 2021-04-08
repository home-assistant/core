"""Support for Nexia / Trane XL Thermostats."""

from nexia.const import UNIT_CELSIUS

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .const import DOMAIN, NEXIA_DEVICE, UPDATE_COORDINATOR
from .entity import NexiaThermostatEntity, NexiaThermostatZoneEntity
from .util import percent_conv


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors for a Nexia device."""

    nexia_data = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home = nexia_data[NEXIA_DEVICE]
    coordinator = nexia_data[UPDATE_COORDINATOR]
    entities = []

    # Thermostat / System Sensors
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)

        entities.append(
            NexiaThermostatSensor(
                coordinator,
                thermostat,
                "get_system_status",
                "System Status",
                None,
                None,
            )
        )
        # Air cleaner
        entities.append(
            NexiaThermostatSensor(
                coordinator,
                thermostat,
                "get_air_cleaner_mode",
                "Air Cleaner Mode",
                None,
                None,
            )
        )
        # Compressor Speed
        if thermostat.has_variable_speed_compressor():
            entities.append(
                NexiaThermostatSensor(
                    coordinator,
                    thermostat,
                    "get_current_compressor_speed",
                    "Current Compressor Speed",
                    None,
                    PERCENTAGE,
                    percent_conv,
                )
            )
            entities.append(
                NexiaThermostatSensor(
                    coordinator,
                    thermostat,
                    "get_requested_compressor_speed",
                    "Requested Compressor Speed",
                    None,
                    PERCENTAGE,
                    percent_conv,
                )
            )
        # Outdoor Temperature
        if thermostat.has_outdoor_temperature():
            unit = (
                TEMP_CELSIUS
                if thermostat.get_unit() == UNIT_CELSIUS
                else TEMP_FAHRENHEIT
            )
            entities.append(
                NexiaThermostatSensor(
                    coordinator,
                    thermostat,
                    "get_outdoor_temperature",
                    "Outdoor Temperature",
                    DEVICE_CLASS_TEMPERATURE,
                    unit,
                )
            )
        # Relative Humidity
        if thermostat.has_relative_humidity():
            entities.append(
                NexiaThermostatSensor(
                    coordinator,
                    thermostat,
                    "get_relative_humidity",
                    "Relative Humidity",
                    DEVICE_CLASS_HUMIDITY,
                    PERCENTAGE,
                    percent_conv,
                )
            )

        # Zone Sensors
        for zone_id in thermostat.get_zone_ids():
            zone = thermostat.get_zone_by_id(zone_id)
            unit = (
                TEMP_CELSIUS
                if thermostat.get_unit() == UNIT_CELSIUS
                else TEMP_FAHRENHEIT
            )
            # Temperature
            entities.append(
                NexiaThermostatZoneSensor(
                    coordinator,
                    zone,
                    "get_temperature",
                    "Temperature",
                    DEVICE_CLASS_TEMPERATURE,
                    unit,
                    None,
                )
            )
            # Zone Status
            entities.append(
                NexiaThermostatZoneSensor(
                    coordinator,
                    zone,
                    "get_status",
                    "Zone Status",
                    None,
                    None,
                )
            )
            # Setpoint Status
            entities.append(
                NexiaThermostatZoneSensor(
                    coordinator,
                    zone,
                    "get_setpoint_status",
                    "Zone Setpoint Status",
                    None,
                    None,
                )
            )

    async_add_entities(entities, True)


class NexiaThermostatSensor(NexiaThermostatEntity, SensorEntity):
    """Provides Nexia thermostat sensor support."""

    def __init__(
        self,
        coordinator,
        thermostat,
        sensor_call,
        sensor_name,
        sensor_class,
        sensor_unit,
        modifier=None,
    ):
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            thermostat,
            name=f"{thermostat.get_name()} {sensor_name}",
            unique_id=f"{thermostat.thermostat_id}_{sensor_call}",
        )
        self._call = sensor_call
        self._class = sensor_class
        self._state = None
        self._unit_of_measurement = sensor_unit
        self._modifier = modifier

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._class

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self._thermostat, self._call)()
        if self._modifier:
            val = self._modifier(val)
        if isinstance(val, float):
            val = round(val, 1)
        return val

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement


class NexiaThermostatZoneSensor(NexiaThermostatZoneEntity, SensorEntity):
    """Nexia Zone Sensor Support."""

    def __init__(
        self,
        coordinator,
        zone,
        sensor_call,
        sensor_name,
        sensor_class,
        sensor_unit,
        modifier=None,
    ):
        """Create a zone sensor."""

        super().__init__(
            coordinator,
            zone,
            name=f"{zone.get_name()} {sensor_name}",
            unique_id=f"{zone.zone_id}_{sensor_call}",
        )
        self._call = sensor_call
        self._class = sensor_class
        self._state = None
        self._unit_of_measurement = sensor_unit
        self._modifier = modifier

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._class

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self._zone, self._call)()
        if self._modifier:
            val = self._modifier(val)
        if isinstance(val, float):
            val = round(val, 1)
        return val

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement
