"""Support for APCUPSd sensors."""
import logging

from apcaccess.status import ALL_UNITS
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_RESOURCES,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
)
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = "UPS "
SENSOR_TYPES = {
    "alarmdel": ["Alarm Delay", "", "mdi:alarm", None],
    "ambtemp": ["Ambient Temperature", "", "mdi:thermometer", None],
    "apc": ["Status Data", "", "mdi:information-outline", None],
    "apcmodel": ["Model", "", "mdi:information-outline", None],
    "badbatts": ["Bad Batteries", "", "mdi:information-outline", None],
    "battdate": ["Battery Replaced", "", "mdi:calendar-clock", None],
    "battstat": ["Battery Status", "", "mdi:information-outline", None],
    "battv": ["Battery Voltage", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "bcharge": ["Battery", PERCENTAGE, "mdi:battery", None],
    "cable": ["Cable Type", "", "mdi:ethernet-cable", None],
    "cumonbatt": ["Total Time on Battery", "", "mdi:timer-outline", None],
    "date": ["Status Date", "", "mdi:calendar-clock", None],
    "dipsw": ["Dip Switch Settings", "", "mdi:information-outline", None],
    "dlowbatt": ["Low Battery Signal", "", "mdi:clock-alert", None],
    "driver": ["Driver", "", "mdi:information-outline", None],
    "dshutd": ["Shutdown Delay", "", "mdi:timer-outline", None],
    "dwake": ["Wake Delay", "", "mdi:timer-outline", None],
    "endapc": ["Date and Time", "", "mdi:calendar-clock", None],
    "extbatts": ["External Batteries", "", "mdi:information-outline", None],
    "firmware": ["Firmware Version", "", "mdi:information-outline", None],
    "hitrans": ["Transfer High", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "hostname": ["Hostname", "", "mdi:information-outline", None],
    "humidity": ["Ambient Humidity", PERCENTAGE, "mdi:water-percent", None],
    "itemp": ["Internal Temperature", TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "lastxfer": ["Last Transfer", "", "mdi:transfer", None],
    "linefail": ["Input Voltage Status", "", "mdi:information-outline", None],
    "linefreq": ["Line Frequency", FREQUENCY_HERTZ, "mdi:information-outline", None],
    "linev": ["Input Voltage", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "loadpct": ["Load", PERCENTAGE, "mdi:gauge", None],
    "loadapnt": ["Load Apparent Power", PERCENTAGE, "mdi:gauge", None],
    "lotrans": ["Transfer Low", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "mandate": ["Manufacture Date", "", "mdi:calendar", None],
    "masterupd": ["Master Update", "", "mdi:information-outline", None],
    "maxlinev": ["Input Voltage High", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "maxtime": ["Battery Timeout", "", "mdi:timer-off-outline", None],
    "mbattchg": ["Battery Shutdown", PERCENTAGE, "mdi:battery-alert", None],
    "minlinev": ["Input Voltage Low", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "mintimel": ["Shutdown Time", "", "mdi:timer-outline", None],
    "model": ["Model", "", "mdi:information-outline", None],
    "nombattv": ["Battery Nominal Voltage", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "nominv": ["Nominal Input Voltage", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "nomoutv": ["Nominal Output Voltage", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "nompower": ["Nominal Output Power", POWER_WATT, "mdi:flash", None],
    "nomapnt": ["Nominal Apparent Power", POWER_VOLT_AMPERE, "mdi:flash", None],
    "numxfers": ["Transfer Count", "", "mdi:counter", None],
    "outcurnt": ["Output Current", ELECTRIC_CURRENT_AMPERE, "mdi:flash", None],
    "outputv": ["Output Voltage", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "reg1": ["Register 1 Fault", "", "mdi:information-outline", None],
    "reg2": ["Register 2 Fault", "", "mdi:information-outline", None],
    "reg3": ["Register 3 Fault", "", "mdi:information-outline", None],
    "retpct": ["Restore Requirement", PERCENTAGE, "mdi:battery-alert", None],
    "selftest": ["Last Self Test", "", "mdi:calendar-clock", None],
    "sense": ["Sensitivity", "", "mdi:information-outline", None],
    "serialno": ["Serial Number", "", "mdi:information-outline", None],
    "starttime": ["Startup Time", "", "mdi:calendar-clock", None],
    "statflag": ["Status Flag", "", "mdi:information-outline", None],
    "status": ["Status", "", "mdi:information-outline", None],
    "stesti": ["Self Test Interval", "", "mdi:information-outline", None],
    "timeleft": ["Time Left", "", "mdi:clock-alert", None],
    "tonbatt": ["Time on Battery", "", "mdi:timer-outline", None],
    "upsmode": ["Mode", "", "mdi:information-outline", None],
    "upsname": ["Name", "", "mdi:information-outline", None],
    "version": ["Daemon Info", "", "mdi:information-outline", None],
    "xoffbat": ["Transfer from Battery", "", "mdi:transfer", None],
    "xoffbatt": ["Transfer from Battery", "", "mdi:transfer", None],
    "xonbatt": ["Transfer to Battery", "", "mdi:transfer", None],
}

SPECIFIC_UNITS = {"ITEMP": TEMP_CELSIUS}
INFERRED_UNITS = {
    " Minutes": TIME_MINUTES,
    " Seconds": TIME_SECONDS,
    " Percent": PERCENTAGE,
    " Volts": ELECTRIC_POTENTIAL_VOLT,
    " Ampere": ELECTRIC_CURRENT_AMPERE,
    " Volt-Ampere": POWER_VOLT_AMPERE,
    " Watts": POWER_WATT,
    " Hz": FREQUENCY_HERTZ,
    " C": TEMP_CELSIUS,
    " Percent Load Capacity": PERCENTAGE,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCES, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the APCUPSd sensors."""
    apcups_data = hass.data[DOMAIN]
    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        if sensor_type not in SENSOR_TYPES:
            SENSOR_TYPES[sensor_type] = [
                sensor_type.title(),
                "",
                "mdi:information-outline",
            ]

        if sensor_type.upper() not in apcups_data.status:
            _LOGGER.warning(
                "Sensor type: %s does not appear in the APCUPSd status output",
                sensor_type,
            )

        entities.append(APCUPSdSensor(apcups_data, sensor_type))

    add_entities(entities, True)


def infer_unit(value):
    """If the value ends with any of the units from ALL_UNITS.

    Split the unit off the end of the value and return the value, unit tuple
    pair. Else return the original value and None as the unit.
    """

    for unit in ALL_UNITS:
        if value.endswith(unit):
            return value[: -len(unit)], INFERRED_UNITS.get(unit, unit.strip())
    return value, None


class APCUPSdSensor(SensorEntity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(self, data, sensor_type):
        """Initialize the sensor."""
        self._data = data
        self.type = sensor_type
        self._attr_name = SENSOR_PREFIX + SENSOR_TYPES[sensor_type][0]
        self._attr_icon = SENSOR_TYPES[self.type][2]
        if SENSOR_TYPES[sensor_type][1]:
            self._attr_unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._attr_device_class = SENSOR_TYPES[sensor_type][3]

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        if self.type.upper() not in self._data.status:
            self._attr_state = None
        else:
            self._attr_state, inferred_unit = infer_unit(
                self._data.status[self.type.upper()]
            )
            if not self._attr_unit_of_measurement:
                self._attr_unit_of_measurement = inferred_unit
