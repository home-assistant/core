"""Support for APCUPSd sensors."""
import logging

from apcaccess.status import ALL_UNITS
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_RESOURCES,
    POWER_WATT,
    TEMP_CELSIUS,
    TIME_MINUTES,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = "UPS "
SENSOR_TYPES = {
    "alarmdel": ["Alarm Delay", "", "mdi:alarm"],
    "ambtemp": ["Ambient Temperature", "", "mdi:thermometer"],
    "apc": ["Status Data", "", "mdi:information-outline"],
    "apcmodel": ["Model", "", "mdi:information-outline"],
    "badbatts": ["Bad Batteries", "", "mdi:information-outline"],
    "battdate": ["Battery Replaced", "", "mdi:calendar-clock"],
    "battstat": ["Battery Status", "", "mdi:information-outline"],
    "battv": ["Battery Voltage", "V", "mdi:flash"],
    "bcharge": ["Battery", UNIT_PERCENTAGE, "mdi:battery"],
    "cable": ["Cable Type", "", "mdi:ethernet-cable"],
    "cumonbatt": ["Total Time on Battery", "", "mdi:timer"],
    "date": ["Status Date", "", "mdi:calendar-clock"],
    "dipsw": ["Dip Switch Settings", "", "mdi:information-outline"],
    "dlowbatt": ["Low Battery Signal", "", "mdi:clock-alert"],
    "driver": ["Driver", "", "mdi:information-outline"],
    "dshutd": ["Shutdown Delay", "", "mdi:timer"],
    "dwake": ["Wake Delay", "", "mdi:timer"],
    "endapc": ["Date and Time", "", "mdi:calendar-clock"],
    "extbatts": ["External Batteries", "", "mdi:information-outline"],
    "firmware": ["Firmware Version", "", "mdi:information-outline"],
    "hitrans": ["Transfer High", "V", "mdi:flash"],
    "hostname": ["Hostname", "", "mdi:information-outline"],
    "humidity": ["Ambient Humidity", UNIT_PERCENTAGE, "mdi:water-percent"],
    "itemp": ["Internal Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "lastxfer": ["Last Transfer", "", "mdi:transfer"],
    "linefail": ["Input Voltage Status", "", "mdi:information-outline"],
    "linefreq": ["Line Frequency", "Hz", "mdi:information-outline"],
    "linev": ["Input Voltage", "V", "mdi:flash"],
    "loadpct": ["Load", UNIT_PERCENTAGE, "mdi:gauge"],
    "loadapnt": ["Load Apparent Power", UNIT_PERCENTAGE, "mdi:gauge"],
    "lotrans": ["Transfer Low", "V", "mdi:flash"],
    "mandate": ["Manufacture Date", "", "mdi:calendar"],
    "masterupd": ["Master Update", "", "mdi:information-outline"],
    "maxlinev": ["Input Voltage High", "V", "mdi:flash"],
    "maxtime": ["Battery Timeout", "", "mdi:timer-off"],
    "mbattchg": ["Battery Shutdown", UNIT_PERCENTAGE, "mdi:battery-alert"],
    "minlinev": ["Input Voltage Low", "V", "mdi:flash"],
    "mintimel": ["Shutdown Time", "", "mdi:timer"],
    "model": ["Model", "", "mdi:information-outline"],
    "nombattv": ["Battery Nominal Voltage", "V", "mdi:flash"],
    "nominv": ["Nominal Input Voltage", "V", "mdi:flash"],
    "nomoutv": ["Nominal Output Voltage", "V", "mdi:flash"],
    "nompower": ["Nominal Output Power", POWER_WATT, "mdi:flash"],
    "nomapnt": ["Nominal Apparent Power", "VA", "mdi:flash"],
    "numxfers": ["Transfer Count", "", "mdi:counter"],
    "outcurnt": ["Output Current", "A", "mdi:flash"],
    "outputv": ["Output Voltage", "V", "mdi:flash"],
    "reg1": ["Register 1 Fault", "", "mdi:information-outline"],
    "reg2": ["Register 2 Fault", "", "mdi:information-outline"],
    "reg3": ["Register 3 Fault", "", "mdi:information-outline"],
    "retpct": ["Restore Requirement", UNIT_PERCENTAGE, "mdi:battery-alert"],
    "selftest": ["Last Self Test", "", "mdi:calendar-clock"],
    "sense": ["Sensitivity", "", "mdi:information-outline"],
    "serialno": ["Serial Number", "", "mdi:information-outline"],
    "starttime": ["Startup Time", "", "mdi:calendar-clock"],
    "statflag": ["Status Flag", "", "mdi:information-outline"],
    "status": ["Status", "", "mdi:information-outline"],
    "stesti": ["Self Test Interval", "", "mdi:information-outline"],
    "timeleft": ["Time Left", "", "mdi:clock-alert"],
    "tonbatt": ["Time on Battery", "", "mdi:timer"],
    "upsmode": ["Mode", "", "mdi:information-outline"],
    "upsname": ["Name", "", "mdi:information-outline"],
    "version": ["Daemon Info", "", "mdi:information-outline"],
    "xoffbat": ["Transfer from Battery", "", "mdi:transfer"],
    "xoffbatt": ["Transfer from Battery", "", "mdi:transfer"],
    "xonbatt": ["Transfer to Battery", "", "mdi:transfer"],
}

SPECIFIC_UNITS = {"ITEMP": TEMP_CELSIUS}
INFERRED_UNITS = {
    " Minutes": TIME_MINUTES,
    " Seconds": TIME_SECONDS,
    " Percent": UNIT_PERCENTAGE,
    " Volts": "V",
    " Ampere": "A",
    " Volt-Ampere": "VA",
    " Watts": POWER_WATT,
    " Hz": "Hz",
    " C": TEMP_CELSIUS,
    " Percent Load Capacity": UNIT_PERCENTAGE,
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


class APCUPSdSensor(Entity):
    """Representation of a sensor entity for APCUPSd status values."""

    def __init__(self, data, sensor_type):
        """Initialize the sensor."""
        self._data = data
        self.type = sensor_type
        self._name = SENSOR_PREFIX + SENSOR_TYPES[sensor_type][0]
        self._unit = SENSOR_TYPES[sensor_type][1]
        self._inferred_unit = None
        self._state = None

    @property
    def name(self):
        """Return the name of the UPS sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def state(self):
        """Return true if the UPS is online, else False."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if not self._unit:
            return self._inferred_unit
        return self._unit

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        if self.type.upper() not in self._data.status:
            self._state = None
            self._inferred_unit = None
        else:
            self._state, self._inferred_unit = infer_unit(
                self._data.status[self.type.upper()]
            )
