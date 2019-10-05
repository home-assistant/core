"""Platform for solarlog sensors."""
import logging
from datetime import timedelta

from requests.exceptions import HTTPError, Timeout
from sunwatcher.solarlog.solarlog import SolarLog
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, POWER_WATT, ENERGY_KILO_WATT_HOUR
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = "solar-log"
DEFAULT_NAME = "solarlog"
SCAN_INTERVAL = timedelta(seconds=60)

"""Supported sensor types."""
SENSOR_TYPES = {
    "time": ["TIME", "last update", None, "mdi:solar-power"],
    "power_ac": ["powerAC", "power AC", POWER_WATT, "mdi:solar-power"],
    "power_dc": ["powerDC", "power DC", POWER_WATT, "mdi:solar-power"],
    "voltage_ac": ["voltageAC", "voltage AC", "V", "mdi:solar-power"],
    "voltage_dc": ["voltageDC", "voltage DC", "V", "mdi:solar-power"],
    "yield_day": ["yieldDAY", "yield day", ENERGY_KILO_WATT_HOUR, "mdi:solar-power"],
    "yield_yesterday": [
        "yieldYESTERDAY",
        "yield yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "yield_month": [
        "yieldMONTH",
        "yield month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "yield_year": ["yieldYEAR", "yield year", ENERGY_KILO_WATT_HOUR, "mdi:solar-power"],
    "yield_total": [
        "yieldTOTAL",
        "yield total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_ac": [
        "consumptionAC",
        "consumption AC",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "consumption_day": [
        "consumptionDAY",
        "consumption day",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_yesterday": [
        "consumptionYESTERDAY",
        "consumption yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_month": [
        "consumptionMONTH",
        "consumption month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_year": [
        "consumptionYEAR",
        "consumption year",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_total": [
        "consumptionTOTAL",
        "consumption total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "total_power": ["totalPOWER", "total power", "Wp", "mdi:solar-power"],
    "alternator_loss": [
        "alternatorLOSS",
        "alternator loss",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "capacity": ["CAPACITY", "capacity", "%", "mdi:solar-power"],
    "efficiency": ["EFFICIENCY", "efficiency", "% W/Wp", "mdi:solar-power"],
    "power_available": [
        "powerAVAILABLE",
        "power available",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "usage": ["USAGE", "usage", None, "mdi:solar-power"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    host = config.get(CONF_HOST)
    platform_name = config.get(CONF_NAME)
    # Set up the API connection to retrieve the data.
    try:
        api = SolarLog(f"http://{host}")
        _LOGGER.debug("Connected to Solarlog API at %s", host)
    except (OSError, HTTPError, Timeout):
        _LOGGER.error(
            "Could not connect to Solarlog API at %s, check host ip address", host
        )
        return

    # Create solarlog data service which will retrieve and update the data.
    data = SolarlogData(hass, api, host)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_key in SENSOR_TYPES:
        sensor = SolarlogSensor(platform_name, sensor_key, data)
        entities.append(sensor)

    add_entities(entities, True)
    return


class SolarlogSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, platform_name, sensor_key, data):
        """Initialize the sensor."""
        self.platform_name = platform_name
        self.sensor_key = sensor_key
        self.data = data
        self._state = None

        self._json_key = SENSOR_TYPES[self.sensor_key][0]
        self._unit_of_measurement = SENSOR_TYPES[self.sensor_key][2]

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} ({})".format(self.platform_name, SENSOR_TYPES[self.sensor_key][1])

    @property
    def unit_of_measurement(self):
        """Return the state of the sensor."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the sensor icon."""
        return SENSOR_TYPES[self.sensor_key][3]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data from the sensor and update the state."""
        self.data.update()
        self._state = self.data.data[self._json_key]


class SolarlogData:
    """Get and update the latest data."""

    def __init__(self, hass, api, host):
        """Initialize the data object."""
        self.api = api
        self.hass = hass
        self.host = host
        self.update = Throttle(SCAN_INTERVAL)(self._update)
        self.data = {}

    def _update(self):
        """Update the data from the Solarlog API."""
        try:
            self.api = SolarLog(f"http://{self.host}")
            response = self.api.time
            _LOGGER.debug(
                "Connection to Solarlog successful. Retrieving latest Solarlog update of %s",
                response,
            )
        except (OSError, Timeout, HTTPError):
            _LOGGER.error("Connection error, Could not retrieve data, skipping update")
            return

        try:
            self.data["TIME"] = self.api.time
            self.data["powerAC"] = self.api.power_ac
            self.data["powerDC"] = self.api.power_dc
            self.data["voltageAC"] = self.api.voltage_ac
            self.data["voltageDC"] = self.api.voltage_dc
            self.data["yieldDAY"] = self.api.yield_day / 1000
            self.data["yieldYESTERDAY"] = self.api.yield_yesterday / 1000
            self.data["yieldMONTH"] = self.api.yield_month / 1000
            self.data["yieldYEAR"] = self.api.yield_year / 1000
            self.data["yieldTOTAL"] = self.api.yield_total / 1000
            self.data["consumptionAC"] = self.api.consumption_ac
            self.data["consumptionDAY"] = self.api.consumption_day / 1000
            self.data["consumptionYESTERDAY"] = self.api.consumption_yesterday / 1000
            self.data["consumptionMONTH"] = self.api.consumption_month / 1000
            self.data["consumptionYEAR"] = self.api.consumption_year / 1000
            self.data["consumptionTOTAL"] = self.api.consumption_total / 1000
            self.data["totalPOWER"] = self.api.total_power
            self.data["alternatorLOSS"] = self.api.alternator_loss
            self.data["CAPACITY"] = round(self.api.capacity * 100, 0)
            self.data["EFFICIENCY"] = round(self.api.efficiency * 100, 0)
            self.data["powerAVAILABLE"] = self.api.power_available
            self.data["USAGE"] = self.api.usage
            _LOGGER.debug("Updated Solarlog overview data: %s", self.data)
        except AttributeError:
            _LOGGER.error("Missing details data in Solarlog response")
