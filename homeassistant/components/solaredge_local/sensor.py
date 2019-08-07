"""
Support for SolarEdge Monitoring API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.solaredge_local/
"""
import logging
from datetime import timedelta

from requests.exceptions import HTTPError, ConnectTimeout
from solaredge_local import SolarEdge
import voluptuous as vol


from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, POWER_WATT, ENERGY_WATT_HOUR
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DOMAIN = "solaredge_local"
UPDATE_DELAY = timedelta(seconds=10)

# Supported sensor types:
# Key: ['json_key', 'name', unit, icon]
SENSOR_TYPES = {
    "lifetime_energy": [
        "energyTotal",
        "Lifetime energy",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "energy_this_year": [
        "energyThisYear",
        "Energy this year",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "energy_this_month": [
        "energyThisMonth",
        "Energy this month",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "energy_today": [
        "energyToday",
        "Energy today",
        ENERGY_WATT_HOUR,
        "mdi:solar-power",
    ],
    "current_power": ["currentPower", "Current Power", POWER_WATT, "mdi:solar-power"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default="SolarEdge"): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the SolarEdge Monitoring API sensor."""
    ip_address = config[CONF_IP_ADDRESS]
    platform_name = config[CONF_NAME]

    # Create new SolarEdge object to retrieve data
    api = SolarEdge("http://{}/".format(ip_address))

    # Check if api can be reached and site is active
    try:
        status = api.get_status()

        status.energy  # pylint: disable=pointless-statement
        _LOGGER.debug("Credentials correct and site is active")
    except AttributeError:
        _LOGGER.error("Missing details data in solaredge response")
        _LOGGER.debug("Response is: %s", status)
        return
    except (ConnectTimeout, HTTPError):
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        return

    # Create solaredge data service which will retrieve and update the data.
    data = SolarEdgeData(hass, api)

    # Create a new sensor for each sensor type.
    entities = []
    for sensor_key in SENSOR_TYPES:
        sensor = SolarEdgeSensor(platform_name, sensor_key, data)
        entities.append(sensor)

    add_entities(entities, True)


class SolarEdgeSensor(Entity):
    """Representation of an SolarEdge Monitoring API sensor."""

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
        """Return the name."""
        return "{} ({})".format(self.platform_name, SENSOR_TYPES[self.sensor_key][1])

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
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


class SolarEdgeData:
    """Get and update the latest data."""

    def __init__(self, hass, api):
        """Initialize the data object."""
        self.hass = hass
        self.api = api
        self.data = {}

    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the SolarEdge Monitoring API."""
        try:
            response = self.api.get_status()
            _LOGGER.debug("response from SolarEdge: %s", response)

            self.data["energyTotal"] = response.energy.total
            self.data["energyThisYear"] = response.energy.thisYear
            self.data["energyThisMonth"] = response.energy.thisMonth
            self.data["energyToday"] = response.energy.today
            self.data["currentPower"] = response.powerWatt

            _LOGGER.debug("Updated SolarEdge overview data: %s", self.data)
        except AttributeError:
            _LOGGER.error("Missing details data in solaredge response")
            _LOGGER.debug("Response is: %s", response)
            return
        except (ConnectTimeout, HTTPError):
            _LOGGER.error("Could not retrieve data, skipping update")
            return

        self.data["energyTotal"] = response.energy.total
        self.data["energyThisYear"] = response.energy.thisYear
        self.data["energyThisMonth"] = response.energy.thisMonth
        self.data["energyToday"] = response.energy.today
        self.data["currentPower"] = response.powerWatt
        _LOGGER.debug("Updated SolarEdge overview data: %s", self.data)
