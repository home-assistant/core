"""
Support for UK Met Office weather service.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.metoffice/
"""

import datapoint

from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, STATE_UNKNOWN, CONF_NAME,
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by the Met Office"
CONF_MO_API_KEY = 'api_key'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=60)
LAST_UPDATE = 0

# Sensor types are defined like: Name, units
SENSOR_TYPES = {
    'name': ['Station Name', None],
    'weather': ['Weather', None],
    'temperature': ['Temperature', TEMP_CELSIUS],
    'feels_like_temperature': ['Feels Like Temperature', TEMP_CELSIUS],
    'wind_speed': ['Wind Speed', 'mps'],
    'wind_direction': ['Wind Direction', None],
    'wind_gust': ['Wind Gust', 'mps'],
    'visibility': ['Visibility', 'km'],
    'uv': ['UV', None],
    'precipitation': ['Probability of Precipitation', '%'],
    'humidity': ['Humidity', '%']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Required(CONF_MO_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    datapoint = datapoint.connection(api_key=config.get(CONF_MO_API_KEY))

    site = datapoint.get_nearest_site(config.get(CONF_LONGITUDE),
                                      config.get(CONF_LATITUDE))

    # Get data
    data = MetOfficeCurrentData(hass, datapoint, site)
    try:
        data.update()
    except ValueError as err:
        _LOGGER.error("Received error from BOM_Current: %s", err)
        return False

    # Add
    add_devices([MetOfficeCurrentSensor(data, variable)
                 for variable in config[CONF_MONITORED_CONDITIONS]])
    return True


class MetOfficeCurrentSensor(Entity):
    """Implementation of a Met Office current sensor."""

    def __init__(self, site, data, condition):
        """Initialize the sensor."""
        self.site = site
        self.data = data
        self._condition = condition

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Met Office {}'.format(SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._condition in self.data.__dict__.keys():
            return getattr(self.data, self._condition)
        else:
            return STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._condition][1]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Sensor Id'] = self._condition
        attr['Site Id'] = self.site.id
        attr['Site Name'] = self.site.name
        attr['Last Update'] = datetime.datetime.strptime(str(
            self.rest.data['local_date_time_full']), '%Y%m%d%H%M%S')
        attr[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        return attr

    def update(self):
        """Update current conditions."""
        self.data.update()


class MetOfficeCurrentData(object):
    """Get data from Datapoint."""

    def __init__(self, hass, datapoint, site):
        """Initialize the data object."""
        self._hass = hass
        self._datapoint = datapoint
        self._site = site
        self.data = None
        self._lastupdate = LAST_UPDATE

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Datapoint."""
        if self._lastupdate != 0 and \
            ((datetime.datetime.now() - self._lastupdate) <
             datetime.timedelta(minutes=35)):
            _LOGGER.info(
                "Met Office was updated %s minutes ago, skipping update as"
                " < 35 minutes", (datetime.datetime.now() - self._lastupdate))
            return self._lastupdate

        try:
            forecast = self._datapoint.get_forecast_for_site(self._site.id, "3hourly")
            self.data = forecast.now()
            self._lastupdate = datetime.datetime.strptime(
                str(self.data['local_date_time_full']), '%Y%m%d%H%M%S')
            return self._lastupdate
        except ValueError as err:
            _LOGGER.error("Check Met Office %s", err.args)
            self.data = None
            raise
