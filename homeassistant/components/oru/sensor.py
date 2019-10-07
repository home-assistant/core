"""Platform for sensor integration."""
import logging
import requests
from homeassistant.const import ENERGY_WATT_HOUR
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_METER = "meter"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    global meter

    add_entities([RealTimeEnergyUsageSensor()])

    meter = str(config.get(CONF_METER, None))
    _LOGGER.debug("meter = %s", meter)


class RealTimeEnergyUsageSensor(Entity):
    """Representation of the sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Real Time Energy Usage"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_WATT_HOUR

    def update(self):
        """Fetch new state data for the sensor."""

        url = (
            "https://oru.opower.com/ei/edge/apis/cws-real-time-ami-v1/cws/oru/meters/"
            + meter
            + "/usage"
        )
        _LOGGER.debug("url = %s", url)

        response = requests.get(url)
        _LOGGER.debug("response = %s", response)

        jsonResponse = response.json()
        _LOGGER.debug("jsonResponse = %s", jsonResponse)

        # parse the return reads and extract the most recent one (i.e. last not None)
        lastRead = None
        for read in jsonResponse["reads"]:
            if read["value"] is None:
                break
            lastRead = read
        _LOGGER.info("lastRead = %s", lastRead)

        val = lastRead["value"]
        _LOGGER.debug("val = %s", val)

        val *= 1000  # transform from KWH in WH
        val = int(round(val))
        _LOGGER.info("val = %s %s", val, self.unit_of_measurement)

        self._state = val
