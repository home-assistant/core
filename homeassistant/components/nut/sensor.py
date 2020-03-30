"""Provides a sensor to track various status aspects of a UPS."""
from datetime import timedelta
import logging

from pynut2.nut2 import PyNUTClient, PyNUTError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_STATE,
    CONF_ALIAS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RESOURCES,
    CONF_USERNAME,
    POWER_WATT,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "NUT UPS"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 3493

KEY_STATUS = "ups.status"
KEY_STATUS_DISPLAY = "ups.status.display"

SCAN_INTERVAL = timedelta(seconds=60)

SENSOR_TYPES = {
    "ups.status.display": ["Status", "", "mdi:information-outline"],
    "ups.status": ["Status Data", "", "mdi:information-outline"],
    "ups.alarm": ["Alarms", "", "mdi:alarm"],
    "ups.time": ["Internal Time", "", "mdi:calendar-clock"],
    "ups.date": ["Internal Date", "", "mdi:calendar"],
    "ups.model": ["Model", "", "mdi:information-outline"],
    "ups.mfr": ["Manufacturer", "", "mdi:information-outline"],
    "ups.mfr.date": ["Manufacture Date", "", "mdi:calendar"],
    "ups.serial": ["Serial Number", "", "mdi:information-outline"],
    "ups.vendorid": ["Vendor ID", "", "mdi:information-outline"],
    "ups.productid": ["Product ID", "", "mdi:information-outline"],
    "ups.firmware": ["Firmware Version", "", "mdi:information-outline"],
    "ups.firmware.aux": ["Firmware Version 2", "", "mdi:information-outline"],
    "ups.temperature": ["UPS Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "ups.load": ["Load", UNIT_PERCENTAGE, "mdi:gauge"],
    "ups.load.high": ["Overload Setting", UNIT_PERCENTAGE, "mdi:gauge"],
    "ups.id": ["System identifier", "", "mdi:information-outline"],
    "ups.delay.start": ["Load Restart Delay", TIME_SECONDS, "mdi:timer"],
    "ups.delay.reboot": ["UPS Reboot Delay", TIME_SECONDS, "mdi:timer"],
    "ups.delay.shutdown": ["UPS Shutdown Delay", TIME_SECONDS, "mdi:timer"],
    "ups.timer.start": ["Load Start Timer", TIME_SECONDS, "mdi:timer"],
    "ups.timer.reboot": ["Load Reboot Timer", TIME_SECONDS, "mdi:timer"],
    "ups.timer.shutdown": ["Load Shutdown Timer", TIME_SECONDS, "mdi:timer"],
    "ups.test.interval": ["Self-Test Interval", TIME_SECONDS, "mdi:timer"],
    "ups.test.result": ["Self-Test Result", "", "mdi:information-outline"],
    "ups.test.date": ["Self-Test Date", "", "mdi:calendar"],
    "ups.display.language": ["Language", "", "mdi:information-outline"],
    "ups.contacts": ["External Contacts", "", "mdi:information-outline"],
    "ups.efficiency": ["Efficiency", UNIT_PERCENTAGE, "mdi:gauge"],
    "ups.power": ["Current Apparent Power", "VA", "mdi:flash"],
    "ups.power.nominal": ["Nominal Power", "VA", "mdi:flash"],
    "ups.realpower": ["Current Real Power", POWER_WATT, "mdi:flash"],
    "ups.realpower.nominal": ["Nominal Real Power", POWER_WATT, "mdi:flash"],
    "ups.beeper.status": ["Beeper Status", "", "mdi:information-outline"],
    "ups.type": ["UPS Type", "", "mdi:information-outline"],
    "ups.watchdog.status": ["Watchdog Status", "", "mdi:information-outline"],
    "ups.start.auto": ["Start on AC", "", "mdi:information-outline"],
    "ups.start.battery": ["Start on Battery", "", "mdi:information-outline"],
    "ups.start.reboot": ["Reboot on Battery", "", "mdi:information-outline"],
    "ups.shutdown": ["Shutdown Ability", "", "mdi:information-outline"],
    "battery.charge": ["Battery Charge", UNIT_PERCENTAGE, "mdi:gauge"],
    "battery.charge.low": ["Low Battery Setpoint", UNIT_PERCENTAGE, "mdi:gauge"],
    "battery.charge.restart": [
        "Minimum Battery to Start",
        UNIT_PERCENTAGE,
        "mdi:gauge",
    ],
    "battery.charge.warning": [
        "Warning Battery Setpoint",
        UNIT_PERCENTAGE,
        "mdi:gauge",
    ],
    "battery.charger.status": ["Charging Status", "", "mdi:information-outline"],
    "battery.voltage": ["Battery Voltage", "V", "mdi:flash"],
    "battery.voltage.nominal": ["Nominal Battery Voltage", "V", "mdi:flash"],
    "battery.voltage.low": ["Low Battery Voltage", "V", "mdi:flash"],
    "battery.voltage.high": ["High Battery Voltage", "V", "mdi:flash"],
    "battery.capacity": ["Battery Capacity", "Ah", "mdi:flash"],
    "battery.current": ["Battery Current", "A", "mdi:flash"],
    "battery.current.total": ["Total Battery Current", "A", "mdi:flash"],
    "battery.temperature": ["Battery Temperature", TEMP_CELSIUS, "mdi:thermometer"],
    "battery.runtime": ["Battery Runtime", TIME_SECONDS, "mdi:timer"],
    "battery.runtime.low": ["Low Battery Runtime", TIME_SECONDS, "mdi:timer"],
    "battery.runtime.restart": [
        "Minimum Battery Runtime to Start",
        TIME_SECONDS,
        "mdi:timer",
    ],
    "battery.alarm.threshold": [
        "Battery Alarm Threshold",
        "",
        "mdi:information-outline",
    ],
    "battery.date": ["Battery Date", "", "mdi:calendar"],
    "battery.mfr.date": ["Battery Manuf. Date", "", "mdi:calendar"],
    "battery.packs": ["Number of Batteries", "", "mdi:information-outline"],
    "battery.packs.bad": ["Number of Bad Batteries", "", "mdi:information-outline"],
    "battery.type": ["Battery Chemistry", "", "mdi:information-outline"],
    "input.sensitivity": ["Input Power Sensitivity", "", "mdi:information-outline"],
    "input.transfer.low": ["Low Voltage Transfer", "V", "mdi:flash"],
    "input.transfer.high": ["High Voltage Transfer", "V", "mdi:flash"],
    "input.transfer.reason": ["Voltage Transfer Reason", "", "mdi:information-outline"],
    "input.voltage": ["Input Voltage", "V", "mdi:flash"],
    "input.voltage.nominal": ["Nominal Input Voltage", "V", "mdi:flash"],
    "input.frequency": ["Input Line Frequency", "hz", "mdi:flash"],
    "input.frequency.nominal": ["Nominal Input Line Frequency", "hz", "mdi:flash"],
    "input.frequency.status": ["Input Frequency Status", "", "mdi:information-outline"],
    "output.current": ["Output Current", "A", "mdi:flash"],
    "output.current.nominal": ["Nominal Output Current", "A", "mdi:flash"],
    "output.voltage": ["Output Voltage", "V", "mdi:flash"],
    "output.voltage.nominal": ["Nominal Output Voltage", "V", "mdi:flash"],
    "output.frequency": ["Output Frequency", "hz", "mdi:flash"],
    "output.frequency.nominal": ["Nominal Output Frequency", "hz", "mdi:flash"],
}

STATE_TYPES = {
    "OL": "Online",
    "OB": "On Battery",
    "LB": "Low Battery",
    "HB": "High Battery",
    "RB": "Battery Needs Replaced",
    "CHRG": "Battery Charging",
    "DISCHRG": "Battery Discharging",
    "BYPASS": "Bypass Active",
    "CAL": "Runtime Calibration",
    "OFF": "Offline",
    "OVER": "Overloaded",
    "TRIM": "Trimming Voltage",
    "BOOST": "Boosting Voltage",
    "FSD": "Forced Shutdown",
    "ALARM": "Alarm",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_ALIAS): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Required(CONF_RESOURCES): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NUT sensors."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]

    alias = config.get(CONF_ALIAS)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    data = PyNUTData(host, port, alias, username, password)

    if data.status is None:
        _LOGGER.error("NUT Sensor has no data, unable to set up")
        raise PlatformNotReady

    _LOGGER.debug("NUT Sensors Available: %s", data.status)

    entities = []

    for resource in config[CONF_RESOURCES]:
        sensor_type = resource.lower()

        # Display status is a special case that falls back to the status value
        # of the UPS instead.
        if sensor_type in data.status or (
            sensor_type == KEY_STATUS_DISPLAY and KEY_STATUS in data.status
        ):
            entities.append(NUTSensor(name, data, sensor_type))
        else:
            _LOGGER.warning(
                "Sensor type: %s does not appear in the NUT status "
                "output, cannot add",
                sensor_type,
            )

    try:
        data.update(no_throttle=True)
    except data.pynuterror as err:
        _LOGGER.error(
            "Failure while testing NUT status retrieval. Cannot continue setup: %s", err
        )
        raise PlatformNotReady

    add_entities(entities, True)


class NUTSensor(Entity):
    """Representation of a sensor entity for NUT status values."""

    def __init__(self, name, data, sensor_type):
        """Initialize the sensor."""
        self._data = data
        self.type = sensor_type
        self._name = "{} {}".format(name, SENSOR_TYPES[sensor_type][0])
        self._unit = SENSOR_TYPES[sensor_type][1]
        self._state = None
        self._display_state = None
        self._available = False

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
        """Return entity state from ups."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def available(self):
        """Return if the device is polling successfully."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the sensor attributes."""
        return {ATTR_STATE: self._display_state}

    def update(self):
        """Get the latest status and use it to update our sensor state."""
        status = self._data.status

        if status is None:
            self._available = False
            return

        self._available = True
        self._display_state = _format_display_state(status)
        # In case of the display status sensor, keep a human-readable form
        # as the sensor state.
        if self.type == KEY_STATUS_DISPLAY:
            self._state = self._display_state
        elif self.type not in status:
            self._state = None
        else:
            self._state = status[self.type]


def _format_display_state(status):
    """Return UPS display state."""
    if status is None:
        return STATE_TYPES["OFF"]
    try:
        return " ".join(STATE_TYPES[state] for state in status[KEY_STATUS].split())
    except KeyError:
        return STATE_UNKNOWN


class PyNUTData:
    """Stores the data retrieved from NUT.

    For each entity to use, acts as the single point responsible for fetching
    updates from the server.
    """

    def __init__(self, host, port, alias, username, password):
        """Initialize the data object."""

        self._host = host
        self._port = port
        self._alias = alias
        self._username = username
        self._password = password

        self.pynuterror = PyNUTError
        # Establish client with persistent=False to open/close connection on
        # each update call.  This is more reliable with async.
        self._client = PyNUTClient(
            self._host, self._port, self._username, self._password, 5, False
        )

        self._status = None

    @property
    def status(self):
        """Get latest update if throttle allows. Return status."""
        self.update()
        return self._status

    def _get_alias(self):
        """Get the ups alias from NUT."""
        try:
            return next(iter(self._client.list_ups()))
        except self.pynuterror as err:
            _LOGGER.error("Failure getting NUT ups alias, %s", err)
            return None

    def _get_status(self):
        """Get the ups status from NUT."""
        if self._alias is None:
            self._alias = self._get_alias()

        try:
            return self._client.list_vars(self._alias)
        except (self.pynuterror, ConnectionResetError) as err:
            _LOGGER.debug("Error getting NUT vars for host %s: %s", self._host, err)
            return None

    def update(self, **kwargs):
        """Fetch the latest status from NUT."""
        self._status = self._get_status()
