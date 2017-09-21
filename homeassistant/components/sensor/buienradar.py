"""
Support for Buienradar.nl weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.buienradar/
"""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS, CONF_NAME, TEMP_CELSIUS)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time)
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['buienradar==0.9']

_LOGGER = logging.getLogger(__name__)

MEASURED_LABEL = 'Measured'
TIMEFRAME_LABEL = 'Timeframe'
SYMBOL = 'symbol'

# Schedule next call after (minutes):
SCHEDULE_OK = 10
# When an error occurred, new call after (minutes):
SCHEDULE_NOK = 2

# Supported sensor types:
# Key: ['label', unit, icon]
SENSOR_TYPES = {
    'stationname': ['Stationname', None, None],
    'condition': ['Condition', None, None],
    'conditioncode': ['Condition code', None, None],
    'conditiondetailed': ['Detailed condition', None, None],
    'conditionexact': ['Full condition', None, None],
    'symbol': ['Symbol', None, None],
    'humidity': ['Humidity', '%', 'mdi:water-percent'],
    'temperature': ['Temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    'groundtemperature': ['Ground temperature', TEMP_CELSIUS,
                          'mdi:thermometer'],
    'windspeed': ['Wind speed', 'm/s', 'mdi:weather-windy'],
    'windforce': ['Wind force', 'Bft', 'mdi:weather-windy'],
    'winddirection': ['Wind direction', None, 'mdi:compass-outline'],
    'windazimuth': ['Wind direction azimuth', '°', 'mdi:compass-outline'],
    'pressure': ['Pressure', 'hPa', 'mdi:gauge'],
    'visibility': ['Visibility', 'm', None],
    'windgust': ['Wind gust', 'm/s', 'mdi:weather-windy'],
    'precipitation': ['Precipitation', 'mm/h', 'mdi:weather-pouring'],
    'irradiance': ['Irradiance', 'W/m2', 'mdi:sunglasses'],
    'precipitation_forecast_average': ['Precipitation forecast average',
                                       'mm/h', 'mdi:weather-pouring'],
    'precipitation_forecast_total': ['Precipitation forecast total',
                                     'mm', 'mdi:weather-pouring'],
    'temperature_1d': ['Temperature 1d', TEMP_CELSIUS, 'mdi:thermometer'],
    'temperature_2d': ['Temperature 2d', TEMP_CELSIUS, 'mdi:thermometer'],
    'temperature_3d': ['Temperature 3d', TEMP_CELSIUS, 'mdi:thermometer'],
    'temperature_4d': ['Temperature 4d', TEMP_CELSIUS, 'mdi:thermometer'],
    'temperature_5d': ['Temperature 5d', TEMP_CELSIUS, 'mdi:thermometer'],
    'mintemp_1d': ['Minimum temperature 1d', TEMP_CELSIUS, 'mdi:thermometer'],
    'mintemp_2d': ['Minimum temperature 2d', TEMP_CELSIUS, 'mdi:thermometer'],
    'mintemp_3d': ['Minimum temperature 3d', TEMP_CELSIUS, 'mdi:thermometer'],
    'mintemp_4d': ['Minimum temperature 4d', TEMP_CELSIUS, 'mdi:thermometer'],
    'mintemp_5d': ['Minimum temperature 5d', TEMP_CELSIUS, 'mdi:thermometer'],
    'rain_1d': ['Rain 1d', 'mm', 'mdi:weather-pouring'],
    'rain_2d': ['Rain 2d', 'mm', 'mdi:weather-pouring'],
    'rain_3d': ['Rain 3d', 'mm', 'mdi:weather-pouring'],
    'rain_4d': ['Rain 4d', 'mm', 'mdi:weather-pouring'],
    'rain_5d': ['Rain 5d', 'mm', 'mdi:weather-pouring'],
    'snow_1d': ['Snow 1d', 'cm', 'mdi:snowflake'],
    'snow_2d': ['Snow 2d', 'cm', 'mdi:snowflake'],
    'snow_3d': ['Snow 3d', 'cm', 'mdi:snowflake'],
    'snow_4d': ['Snow 4d', 'cm', 'mdi:snowflake'],
    'snow_5d': ['Snow 5d', 'cm', 'mdi:snowflake'],
    'rainchance_1d': ['Rainchance 1d', '%', 'mdi:weather-pouring'],
    'rainchance_2d': ['Rainchance 2d', '%', 'mdi:weather-pouring'],
    'rainchance_3d': ['Rainchance 3d', '%', 'mdi:weather-pouring'],
    'rainchance_4d': ['Rainchance 4d', '%', 'mdi:weather-pouring'],
    'rainchance_5d': ['Rainchance 5d', '%', 'mdi:weather-pouring'],
    'sunchance_1d': ['Sunchance 1d', '%', 'mdi:weather-partlycloudy'],
    'sunchance_2d': ['Sunchance 2d', '%', 'mdi:weather-partlycloudy'],
    'sunchance_3d': ['Sunchance 3d', '%', 'mdi:weather-partlycloudy'],
    'sunchance_4d': ['Sunchance 4d', '%', 'mdi:weather-partlycloudy'],
    'sunchance_5d': ['Sunchance 5d', '%', 'mdi:weather-partlycloudy'],
    'windforce_1d': ['Wind force 1d', 'Bft', 'mdi:weather-windy'],
    'windforce_2d': ['Wind force 2d', 'Bft', 'mdi:weather-windy'],
    'windforce_3d': ['Wind force 3d', 'Bft', 'mdi:weather-windy'],
    'windforce_4d': ['Wind force 4d', 'Bft', 'mdi:weather-windy'],
    'windforce_5d': ['Wind force 5d', 'Bft', 'mdi:weather-windy'],
    'condition_1d': ['Condition 1d', None, None],
    'condition_2d': ['Condition 2d', None, None],
    'condition_3d': ['Condition 3d', None, None],
    'condition_4d': ['Condition 4d', None, None],
    'condition_5d': ['Condition 5d', None, None],
    'conditioncode_1d': ['Condition code 1d', None, None],
    'conditioncode_2d': ['Condition code 2d', None, None],
    'conditioncode_3d': ['Condition code 3d', None, None],
    'conditioncode_4d': ['Condition code 4d', None, None],
    'conditioncode_5d': ['Condition code 5d', None, None],
    'conditiondetailed_1d': ['Detailed condition 1d', None, None],
    'conditiondetailed_2d': ['Detailed condition 2d', None, None],
    'conditiondetailed_3d': ['Detailed condition 3d', None, None],
    'conditiondetailed_4d': ['Detailed condition 4d', None, None],
    'conditiondetailed_5d': ['Detailed condition 5d', None, None],
    'conditionexact_1d': ['Full condition 1d', None, None],
    'conditionexact_2d': ['Full condition 2d', None, None],
    'conditionexact_3d': ['Full condition 3d', None, None],
    'conditionexact_4d': ['Full condition 4d', None, None],
    'conditionexact_5d': ['Full condition 5d', None, None],
    'symbol_1d': ['Symbol 1d', None, None],
    'symbol_2d': ['Symbol 2d', None, None],
    'symbol_3d': ['Symbol 3d', None, None],
    'symbol_4d': ['Symbol 4d', None, None],
    'symbol_5d': ['Symbol 5d', None, None],
}

CONF_TIMEFRAME = 'timeframe'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=['symbol', 'temperature']): vol.All(
                     cv.ensure_list, vol.Length(min=1),
                     [vol.In(SENSOR_TYPES.keys())]),
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_TIMEFRAME, default=60):
        vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Create the buienradar sensor."""
    from homeassistant.components.weather.buienradar import DEFAULT_TIMEFRAME

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    timeframe = config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in HomeAssistant config")
        return False

    coordinates = {CONF_LATITUDE: float(latitude),
                   CONF_LONGITUDE: float(longitude)}

    _LOGGER.debug("Initializing buienradar sensor coordinate %s, timeframe %s",
                  coordinates, timeframe)

    dev = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        dev.append(BrSensor(sensor_type, config.get(CONF_NAME, 'br')))
    async_add_devices(dev)

    data = BrData(hass, coordinates, timeframe, dev)
    # schedule the first update in 1 minute from now:
    yield from data.schedule_update(1)


class BrSensor(Entity):
    """Representation of an Buienradar sensor."""

    def __init__(self, sensor_type, client_name):
        """Initialize the sensor."""
        from buienradar.buienradar import (PRECIPITATION_FORECAST)

        self.client_name = client_name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._entity_picture = None
        self._attribution = None
        self._measured = None
        self._stationname = None

        if self.type.startswith(PRECIPITATION_FORECAST):
            self._timeframe = None

    def load_data(self, data):
        """Load the sensor with relevant data."""
        # Find sensor
        from buienradar.buienradar import (ATTRIBUTION, CONDITION, CONDCODE,
                                           DETAILED, EXACT, EXACTNL, FORECAST,
                                           IMAGE, MEASURED,
                                           PRECIPITATION_FORECAST, STATIONNAME,
                                           TIMEFRAME)

        self._attribution = data.get(ATTRIBUTION)
        self._stationname = data.get(STATIONNAME)
        self._measured = data.get(MEASURED)

        if self.type.endswith('_1d') or \
           self.type.endswith('_2d') or \
           self.type.endswith('_3d') or \
           self.type.endswith('_4d') or \
           self.type.endswith('_5d'):

            fcday = 0
            if self.type.endswith('_2d'):
                fcday = 1
            if self.type.endswith('_3d'):
                fcday = 2
            if self.type.endswith('_4d'):
                fcday = 3
            if self.type.endswith('_5d'):
                fcday = 4

            # update all other sensors
            if self.type.startswith(SYMBOL) or self.type.startswith(CONDITION):
                try:
                    condition = data.get(FORECAST)[fcday].get(CONDITION)
                except IndexError:
                    _LOGGER.warning("No forecast for fcday=%s...", fcday)
                    return False

                if condition:
                    new_state = condition.get(CONDITION, None)
                    if self.type.startswith(SYMBOL):
                        new_state = condition.get(EXACTNL, None)
                    if self.type.startswith('conditioncode'):
                        new_state = condition.get(CONDCODE, None)
                    if self.type.startswith('conditiondetailed'):
                        new_state = condition.get(DETAILED, None)
                    if self.type.startswith('conditionexact'):
                        new_state = condition.get(EXACT, None)

                    img = condition.get(IMAGE, None)

                    if new_state != self._state or img != self._entity_picture:
                        self._state = new_state
                        self._entity_picture = img
                        return True
                return False
            else:
                try:
                    new_state = data.get(FORECAST)[fcday].get(self.type[:-3])
                except IndexError:
                    _LOGGER.warning("No forecast for fcday=%s...", fcday)
                    return False

                if new_state != self._state:
                    self._state = new_state
                    return True
                return False

            return False

        if self.type == SYMBOL or self.type.startswith(CONDITION):
            # update weather symbol & status text
            condition = data.get(CONDITION, None)
            if condition:
                if self.type == SYMBOL:
                    new_state = condition.get(EXACTNL, None)
                if self.type == CONDITION:
                    new_state = condition.get(CONDITION, None)
                if self.type == 'conditioncode':
                    new_state = condition.get(CONDCODE, None)
                if self.type == 'conditiondetailed':
                    new_state = condition.get(DETAILED, None)
                if self.type == 'conditionexact':
                    new_state = condition.get(EXACT, None)

                img = condition.get(IMAGE, None)

                # pylint: disable=protected-access
                if new_state != self._state or img != self._entity_picture:
                    self._state = new_state
                    self._entity_picture = img
                    return True

            return False

        if self.type.startswith(PRECIPITATION_FORECAST):
            # update nested precipitation forecast sensors
            nested = data.get(PRECIPITATION_FORECAST)
            new_state = nested.get(self.type[len(PRECIPITATION_FORECAST)+1:])
            self._timeframe = nested.get(TIMEFRAME)
            # pylint: disable=protected-access
            if new_state != self._state:
                self._state = new_state
                return True
            return False

        # update all other sensors
        new_state = data.get(self.type)
        # pylint: disable=protected-access
        if new_state != self._state:
            self._state = new_state
            return True
        return False

    @property
    def attribution(self):
        """Return the attribution."""
        return self._attribution

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def should_poll(self):  # pylint: disable=no-self-use
        """No polling needed."""
        return False

    @property
    def entity_picture(self):
        """Weather symbol if type is symbol."""
        return self._entity_picture

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        from buienradar.buienradar import (PRECIPITATION_FORECAST)

        if self.type.startswith(PRECIPITATION_FORECAST):
            result = {ATTR_ATTRIBUTION: self._attribution}
            if self._timeframe is not None:
                result[TIMEFRAME_LABEL] = "%d min" % (self._timeframe)

            return result

        result = {
            ATTR_ATTRIBUTION: self._attribution,
            SENSOR_TYPES['stationname'][0]: self._stationname,
        }
        if self._measured is not None:
            # convert datetime (Europe/Amsterdam) into local datetime
            local_dt = dt_util.as_local(self._measured)
            result[MEASURED_LABEL] = local_dt.strftime("%c")

        return result

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return possible sensor specific icon."""
        return SENSOR_TYPES[self.type][2]


class BrData(object):
    """Get the latest data and updates the states."""

    def __init__(self, hass, coordinates, timeframe, devices):
        """Initialize the data object."""
        self.devices = devices
        self.data = {}
        self.hass = hass
        self.coordinates = coordinates
        self.timeframe = timeframe

    @asyncio.coroutine
    def update_devices(self):
        """Update all devices/sensors."""
        if self.devices:
            tasks = []
            # Update all devices
            for dev in self.devices:
                if dev.load_data(self.data):
                    tasks.append(dev.async_update_ha_state())

            if tasks:
                yield from asyncio.wait(tasks, loop=self.hass.loop)

    @asyncio.coroutine
    def schedule_update(self, minute=1):
        """Schedule an update after minute minutes."""
        _LOGGER.debug("Scheduling next update in %s minutes.", minute)
        nxt = dt_util.utcnow() + timedelta(minutes=minute)
        async_track_point_in_utc_time(self.hass, self.async_update,
                                      nxt)

    @asyncio.coroutine
    def get_data(self, url):
        """Load data from specified url."""
        from buienradar.buienradar import (CONTENT,
                                           MESSAGE, STATUS_CODE, SUCCESS)

        _LOGGER.debug("Calling url: %s...", url)
        result = {SUCCESS: False, MESSAGE: None}
        resp = None
        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10, loop=self.hass.loop):
                resp = yield from websession.get(url)

                result[STATUS_CODE] = resp.status
                result[CONTENT] = yield from resp.text()
                if resp.status == 200:
                    result[SUCCESS] = True
                else:
                    result[MESSAGE] = "Got http statuscode: %d" % (resp.status)

                return result
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            result[MESSAGE] = "%s" % err
            return result
        finally:
            if resp is not None:
                yield from resp.release()

    @asyncio.coroutine
    def async_update(self, *_):
        """Update the data from buienradar."""
        from buienradar.buienradar import (parse_data, CONTENT,
                                           DATA, MESSAGE, STATUS_CODE, SUCCESS)

        content = yield from self.get_data('http://xml.buienradar.nl')
        if not content.get(SUCCESS, False):
            content = yield from self.get_data('http://api.buienradar.nl')

        if content.get(SUCCESS) is not True:
            # unable to get the data
            _LOGGER.warning("Unable to retrieve xml data from Buienradar."
                            "(Msg: %s, status: %s,)",
                            content.get(MESSAGE),
                            content.get(STATUS_CODE),)
            # schedule new call
            yield from self.schedule_update(SCHEDULE_NOK)
            return

        # rounding coordinates prevents unnecessary redirects/calls
        rainurl = 'http://gadgets.buienradar.nl/data/raintext/?lat={}&lon={}'
        rainurl = rainurl.format(
            round(self.coordinates[CONF_LATITUDE], 2),
            round(self.coordinates[CONF_LONGITUDE], 2)
            )
        raincontent = yield from self.get_data(rainurl)

        if raincontent.get(SUCCESS) is not True:
            # unable to get the data
            _LOGGER.warning("Unable to retrieve raindata from Buienradar."
                            "(Msg: %s, status: %s,)",
                            raincontent.get(MESSAGE),
                            raincontent.get(STATUS_CODE),)
            # schedule new call
            yield from self.schedule_update(SCHEDULE_NOK)
            return

        result = parse_data(content.get(CONTENT),
                            raincontent.get(CONTENT),
                            self.coordinates[CONF_LATITUDE],
                            self.coordinates[CONF_LONGITUDE],
                            self.timeframe)

        _LOGGER.debug("Buienradar parsed data: %s", result)
        if result.get(SUCCESS) is not True:
            _LOGGER.warning("Unable to parse data from Buienradar."
                            "(Msg: %s)",
                            result.get(MESSAGE),)
            yield from self.schedule_update(SCHEDULE_NOK)
            return

        self.data = result.get(DATA)
        yield from self.update_devices()
        yield from self.schedule_update(SCHEDULE_OK)

    @property
    def attribution(self):
        """Return the attribution."""
        from buienradar.buienradar import ATTRIBUTION
        return self.data.get(ATTRIBUTION)

    @property
    def stationname(self):
        """Return the name of the selected weatherstation."""
        from buienradar.buienradar import STATIONNAME
        return self.data.get(STATIONNAME)

    @property
    def condition(self):
        """Return the condition."""
        from buienradar.buienradar import CONDITION
        return self.data.get(CONDITION)

    @property
    def temperature(self):
        """Return the temperature, or None."""
        from buienradar.buienradar import TEMPERATURE
        try:
            return float(self.data.get(TEMPERATURE))
        except (ValueError, TypeError):
            return None

    @property
    def pressure(self):
        """Return the pressure, or None."""
        from buienradar.buienradar import PRESSURE
        try:
            return float(self.data.get(PRESSURE))
        except (ValueError, TypeError):
            return None

    @property
    def humidity(self):
        """Return the humidity, or None."""
        from buienradar.buienradar import HUMIDITY
        try:
            return int(self.data.get(HUMIDITY))
        except (ValueError, TypeError):
            return None

    @property
    def visibility(self):
        """Return the visibility, or None."""
        from buienradar.buienradar import VISIBILITY
        try:
            return int(self.data.get(VISIBILITY))
        except (ValueError, TypeError):
            return None

    @property
    def wind_speed(self):
        """Return the windspeed, or None."""
        from buienradar.buienradar import WINDSPEED
        try:
            return float(self.data.get(WINDSPEED))
        except (ValueError, TypeError):
            return None

    @property
    def wind_bearing(self):
        """Return the wind bearing, or None."""
        from buienradar.buienradar import WINDAZIMUTH
        try:
            return int(self.data.get(WINDAZIMUTH))
        except (ValueError, TypeError):
            return None

    @property
    def forecast(self):
        """Return the forecast data."""
        from buienradar.buienradar import FORECAST
        return self.data.get(FORECAST)
