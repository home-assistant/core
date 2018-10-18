"""
Support for Meteo France raining forecast.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.meteofrance/
"""
import voluptuous as vol
import logging
import datetime
import json
import requests

from homeassistant.components.sensor import PLATFORM_SCHEMA


from homeassistant.const import (
    STATE_UNKNOWN, TEMP_CELSIUS, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_RESOURCE = 'http://www.meteofrance.com/mf3-rpc-portlet/rest/pluie/{}/'
_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by Meteo France"
CONF_LOCATION_ID = 'location_id'
CONF_NAME = 'name'

STATE_ATTR_FORECAST = 'Forecast'
STATE_ATTR_FORECAST_INTERVAL = 'Interval_'

SCAN_INTERVAL = datetime.timedelta(minutes=5)
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=5)
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LOCATION_ID): cv.string,
    vol.Optional(CONF_NAME): cv.string
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    location_id = config.get(CONF_LOCATION_ID)
    if len(location_id) == 5: #convert insee code to needed meteofrance code
        location_id = str(location_id)+'0'
    location_name = config.get(CONF_NAME)
    meteofrance_data = MeteoFranceCurrentData(hass, location_id)

    try:
        meteofrance_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from Meteo France: %s", err)
        return False

    add_devices([MeteoFranceSensor(meteofrance_data,location_name)])



class MeteoFranceSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, meteofrance_data, location_name):
        """Initialize the sensor."""
        self.meteofrance_data = meteofrance_data
        self.location_name = location_name
        self._unit = "Min"

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.location_name is None:
            return "1hr rain forecast"
        return "{} 1hr rain forecast".format(self.location_name)

    @property
    def state(self):
        """Return the state of the sensor."""

        if self.meteofrance_data and self.meteofrance_data.rain_forecast:
            self._timeToRain = 0;
            for interval in self.meteofrance_data.rain_forecast_data:
                if interval["niveauPluie"]>1:
                    self._unit = "Min"
                    return self._timeToRain
                self._timeToRain += 5
            self._unit = ""
            return "No rain"

        return STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the state attributes of the sun."""
        if self.meteofrance_data and self.meteofrance_data.rain_forecast:
            return {
                    **{
                    STATE_ATTR_FORECAST: self.meteofrance_data.rain_forecast,
                    },
                    **{STATE_ATTR_FORECAST_INTERVAL+str(interval+1): self.meteofrance_data.rain_forecast_data[interval]["niveauPluie"]
                        for interval in range(0,len(self.meteofrance_data.rain_forecast_data))
                    },
                    **{
                    ATTR_ATTRIBUTION: CONF_ATTRIBUTION
                    }
                }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    def update(self):
        """Fetch new state data for the sensor."""
        self.meteofrance_data.update()


class MeteoFranceCurrentData(object):
    """Get data from Meteo France."""

    def __init__(self, hass, location_id):
        """Initialize the data object."""
        self._hass = hass
        self._location_id = location_id
        self.rain_forecast = None

    def _build_url(self):
        url = _RESOURCE.format(self._location_id)
        _LOGGER.info("Meteo France rain forecast URL %s", url)
        return url

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from BOM."""
        try:
            result = requests.get(self._build_url(), timeout=10).json()
            if result['hasData'] is True:
                self.rain_forecast = result["niveauPluieText"][0]
                self.rain_forecast_data = result["dataCadran"]
            else:
                raise ValueError("No forecast for this location: {}".format(self._location_id))
        except ValueError as err:
            _LOGGER.error("Meteo-France component: %s", err.args)
            raise
