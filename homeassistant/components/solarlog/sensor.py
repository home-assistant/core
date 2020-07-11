"""Platform for solarlog sensors."""
import logging
from urllib.parse import ParseResult, urlparse

from requests.exceptions import HTTPError, Timeout
from sunwatcher.solarlog.solarlog import SolarLog
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN, SCAN_INTERVAL, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import YAML configuration when available."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
        )
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Add solarlog entry."""
    host_entry = entry.data[CONF_HOST]

    url = urlparse(host_entry, "http")
    netloc = url.netloc or url.path
    path = url.path if url.netloc else ""
    url = ParseResult("http", netloc, path, *url[3:])
    host = url.geturl()

    platform_name = entry.title

    try:
        api = await hass.async_add_executor_job(SolarLog, host)
        _LOGGER.debug("Connected to Solar-Log device, setting up entries")
    except (OSError, HTTPError, Timeout):
        _LOGGER.error(
            "Could not connect to Solar-Log device at %s, check host ip address", host
        )
        return

    # Create solarlog data service which will retrieve and update the data.
    data = await hass.async_add_executor_job(SolarlogData, hass, api, host)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_key in SENSOR_TYPES:
        sensor = SolarlogSensor(platform_name, sensor_key, data)
        entities.append(sensor)

    async_add_entities(entities, True)
    return True


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
        """Update the data from the SolarLog device."""
        try:
            self.api = SolarLog(self.host)
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
