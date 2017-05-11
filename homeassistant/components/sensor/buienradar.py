"""
Support for Buienradar.nl weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.buienradar/
"""
import asyncio
import logging
from datetime import datetime, time, timedelta
import time as tm
from xml.parsers.expat import ExpatError

import async_timeout
import aiohttp
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_MONITORED_CONDITIONS,
    ATTR_ATTRIBUTION, ATTR_TEMPERATURE)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_time_interval)
from homeassistant.util import dt as dt_util
from homeassistant.util.location import distance

REQUIREMENTS = ['xmltodict==0.11.0']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by buienradar.nl"
CONF_DATETIME = 'datetime'
CONF_STATIONNAME = 'stationname'
CONF_SYMBOL = 'symbol'
CONF_HUMIDITY = 'humidity'
CONF_GROUNDTEMP = 'groundtemperature'
CONF_WINDSPEED = 'windspeed'
CONF_WINDFORCE = 'windforce'
CONF_WINDDIRECTION = 'winddirection'
CONF_WINDAZIMUTH = 'windazimuth'
CONF_PRESSURE = 'pressure'
CONF_VISIBILITY = 'visibility'
CONF_WINDGUST = 'windgust'
CONF_PRECIPITATION = 'precipitation'
CONF_IRRADIANCE = 'irradiance'
CONF_FORECAST = 'forecast'

# key names in buienradar xml:
CONF_BR_ROOT = 'buienradarnl'
CONF_BR_WEERGEGEVENS = 'weergegevens'
CONF_BR_ACTUEELWEER = 'actueel_weer'
CONF_BR_WEERSTATIONS = 'weerstations'
CONF_BR_WEERSTATION = 'weerstation'
CONF_BR_LAT = 'lat'
CONF_BR_LON = 'lon'
CONF_BR_STATIONCODE = 'stationcode'
CONF_BR_STATIONNAME = 'stationnaam'
CONF_BR_TEXT = '#text'
CONF_BR_ZIN = '@zin'
CONF_BR_IMG = '_img'
CONF_BR_FORECAST = 'verwachting_meerdaags'
CONF_BR_DAYFC = "dag-plus%d"
CONF_BR_MINTEMP = 'maxtemp'
CONF_BR_MAXTEMP = 'maxtempmax'

# Sensor types are defined like so:
# SENSOR_TYPES = { 'key': ['Display name',
#                          'unit of measurement',
#                          'key in buienradar xml'],}
SENSOR_TYPES = {
    CONF_STATIONNAME: ['Stationname', None, 'stationnaam'],
    CONF_SYMBOL: ['Symbol', None, 'icoonactueel'],
    CONF_HUMIDITY: ['Humidity', '%', 'luchtvochtigheid'],
    ATTR_TEMPERATURE: ['Temperature', '°C', 'temperatuurGC'],
    CONF_GROUNDTEMP: ['Ground Temperature', '°C', 'temperatuur10cm'],
    CONF_WINDSPEED: ['Wind speed', 'm/s', 'windsnelheidMS'],
    CONF_WINDFORCE: ['Wind force', 'Bft', 'windsnelheidBF'],
    CONF_WINDDIRECTION: ['Wind direction', '°', 'windrichtingGR'],
    CONF_WINDAZIMUTH: ['Wind direction azimuth', None, 'windrichting'],
    CONF_PRESSURE: ['Pressure', 'hPa', 'luchtdruk'],
    CONF_VISIBILITY: ['Visibility', 'm', 'zichtmeters'],
    CONF_WINDGUST: ['Wind gust', 'm/s', 'windstotenMS'],
    CONF_PRECIPITATION: ['Precipitation', 'mm/h', 'regenMMPU'],
    CONF_IRRADIANCE: ['Irradiance', 'W/m2', 'zonintensiteitWM2'],
}

SENSOR_ICONS = {
    CONF_HUMIDITY: 'mdi:water-percent',
    ATTR_TEMPERATURE: 'mdi:thermometer',
    CONF_GROUNDTEMP: 'mdi:thermometer',
    CONF_WINDSPEED: 'mdi:weather-windy',
    CONF_WINDFORCE: 'mdi:weather-windy',
    CONF_WINDDIRECTION: 'mdi:compass-outline',
    CONF_WINDAZIMUTH: 'mdi:compass-outline',
    CONF_PRESSURE: 'mdi:gauge',
    CONF_WINDGUST: 'mdi:weather-windy',
    CONF_IRRADIANCE: 'mdi:sunglasses',
    CONF_PRECIPITATION: 'mdi:weather-pouring',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=[CONF_SYMBOL, ATTR_TEMPERATURE]): vol.All(
                     cv.ensure_list, vol.Length(min=1),
                     [vol.In(SENSOR_TYPES.keys())]),
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the buienradar_nl sensor."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in HomeAssistant config")
        return False

    coordinates = {CONF_LATITUDE: float(latitude),
                   CONF_LONGITUDE: float(longitude)}

    dev = []
    for sensor_type in config[CONF_MONITORED_CONDITIONS]:
        dev.append(BrSensor(sensor_type))
    async_add_devices(dev)

    weather = BrData(hass, coordinates, dev)
    # Update weather every 10 minutes, since
    # the data gets updated every 10 minutes
    async_track_time_interval(hass, weather.async_update,
                              timedelta(minutes=10))
    yield from weather.async_update()


class BrSensor(Entity):
    """Representation of an Buienradar sensor."""

    def __init__(self, sensor_type):
        """Initialize the sensor."""
        self.client_name = 'br'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self._entity_picture = None

    def load_data(self, data):
        """Load the sensor with relevant data."""
        # Find sensor
        if self.type == CONF_SYMBOL:
            # update weather symbol & status text
            new_state = data[self.type]
            img = data[self.type + CONF_BR_IMG]

            # pylint: disable=protected-access
            if new_state != self._state or img != self._entity_picture:
                self._state = new_state
                self._entity_picture = img
                return True
        else:
            # update all other sensors
            new_state = data[self.type]
            # pylint: disable=protected-access
            if new_state != self._state:
                self._state = new_state
                return True

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
        if self.type != 'symbol':
            return None
        else:
            return self._entity_picture

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return possible sensor specific icon."""
        if self.type in SENSOR_ICONS:
            return SENSOR_ICONS[self.type]


class BrData(object):
    """Get the latest data and updates the states."""

    def __init__(self, hass, coordinates, devices):
        """Initialize the data object."""
        self._url = 'https://xml.buienradar.nl/'
        self.devices = devices
        self.data = {}
        self.hass = hass
        self.coordinates = coordinates
        self.weatherstation = None

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
    def async_update(self, *_):
        """Update the data from buienradar."""
        def get_temp(section):
            """Get the forecasted temp from xml section."""
            try:
                return (float(section[CONF_BR_MINTEMP]) +
                        float(section[CONF_BR_MAXTEMP])) / 2
            except (ValueError, TypeError, KeyError):
                return None

        def select_nearest_ws(xmldata):
            """Select the nearest weatherstation."""
            dist = 0
            loc_data = None

            xmldata_tmp = xmldata
            if CONF_BR_WEERGEGEVENS not in xmldata_tmp:
                # no section with weatherdata
                _LOGGER.warning("Missing section in Buienradar xmldata (%s)."
                                "Can happen 00:00-01:00 CE(S)T",
                                CONF_BR_WEERGEGEVENS)
                return None

            xmldata_tmp = xmldata_tmp[CONF_BR_WEERGEGEVENS]
            if CONF_BR_ACTUEELWEER not in xmldata_tmp:
                # no section current weather
                _LOGGER.warning("Missing section in Buienradar xmldata (%s)."
                                "Can happen 00:00-01:00 CE(S)T",
                                CONF_BR_ACTUEELWEER)
                return None

            xmldata_tmp = xmldata_tmp[CONF_BR_ACTUEELWEER]
            if CONF_BR_WEERSTATIONS not in xmldata_tmp:
                # no section with weather stations
                _LOGGER.warning("Missing section in Buienradar xmldata (%s)."
                                "Can happen 00:00-01:00 CE(S)T",
                                CONF_BR_WEERSTATIONS)
                return None

            xmldata_tmp = xmldata_tmp[CONF_BR_WEERSTATIONS]
            if CONF_BR_WEERSTATION not in xmldata_tmp:
                # no weatherstation section(s)
                _LOGGER.warning("Missing section in Buienradar xmldata (%s)."
                                "Can happen 00:00-01:00 CE(S)T",
                                CONF_BR_WEERSTATION)
                return None

            xmldata_tmp = xmldata_tmp[CONF_BR_WEERSTATION]
            for wstation in xmldata_tmp:
                wslat = float(wstation[CONF_BR_LAT])
                wslon = float(wstation[CONF_BR_LON])

                if ((loc_data is None) or (
                        distance(self.coordinates[CONF_LATITUDE],
                                 self.coordinates[CONF_LONGITUDE],
                                 wslat,
                                 wslon) < dist)):
                    dist = distance(self.coordinates[CONF_LATITUDE],
                                    self.coordinates[CONF_LONGITUDE],
                                    wslat, wslon)
                    self.weatherstation = wstation[CONF_BR_STATIONCODE]
                    loc_data = wstation

            if loc_data is None:
                _LOGGER.warning("No weatherstation selected; aborting update.")
                return None
            else:
                _LOGGER.debug("Selected station: code='%s', "
                              "name='%s', lat='%s', lon='%s'.",
                              loc_data[CONF_BR_STATIONCODE],
                              loc_data[CONF_BR_STATIONNAME][CONF_BR_TEXT],
                              loc_data[CONF_BR_LAT],
                              loc_data[CONF_BR_LON])
                return loc_data

        def try_again(err: str):
            """Retry in 2 minutes."""
            _LOGGER.warning('Retrying in 2 minutes: %s', err)
            nxt = dt_util.utcnow() + timedelta(minutes=2)
            async_track_point_in_utc_time(self.hass, self.async_update,
                                          nxt)

        def local_time_offset(convt=None):
            """Return offset of local zone from UTC."""
            # python2.3 localtime() can't take None
            if convt is None:
                convt = tm.time()

            if tm.localtime(convt).tm_isdst and tm.daylight:
                _LOGGER.debug('local_time_offset: %s', -tm.altzone)
                return -tm.altzone
            else:
                _LOGGER.debug('local_time_offset: %s', -tm.timezone)
                return -tm.timezone

        # get weather data
        resp = None
        try:
            websession = async_get_clientsession(self.hass)
            with async_timeout.timeout(10, loop=self.hass.loop):
                resp = yield from websession.get(self._url)
            if resp.status != 200:
                try_again('{} returned {}'.format(resp.url, resp.status))
                return
            text = yield from resp.text()
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            try_again(err)
            return
        finally:
            if resp is not None:
                yield from resp.release()

        # convert to to dictionary
        try:
            import xmltodict
            xmldata = xmltodict.parse(text)[CONF_BR_ROOT]
        except (ExpatError, IndexError) as err:
            try_again(err)
            return

        # select the nearest ws from the data
        loc_data = select_nearest_ws(xmldata)
        if loc_data:
            # update the data
            # pylint: disable=unused-variable
            for key, value in SENSOR_TYPES.items():
                self.data[key] = None
                try:
                    sens_data = loc_data[SENSOR_TYPES[key][2]]
                    if key == CONF_SYMBOL:
                        # update weather symbol & status text
                        self.data[key] = sens_data[CONF_BR_ZIN]
                        self.data[key + CONF_BR_IMG] = sens_data[CONF_BR_TEXT]
                    else:
                        # update all other data
                        if key == CONF_STATIONNAME:
                            self.data[key] = sens_data[CONF_BR_TEXT]
                        else:
                            self.data[key] = sens_data
                except KeyError:
                    _LOGGER.warning("Data element with key='%s' "
                                    "not loaded from br data!", key)
            _LOGGER.debug("BR cached data: %s", self.data)

        # forecast data
        self.data[CONF_FORECAST] = []

        if CONF_BR_WEERGEGEVENS in xmldata:
            section = xmldata[CONF_BR_WEERGEGEVENS]
            if CONF_BR_FORECAST in section:
                section = section[CONF_BR_FORECAST]
                for daycnt in range(1, 6):
                    daysection = CONF_BR_DAYFC % daycnt
                    if daysection in section:
                        tmpsect = section[daysection]
                        # tomorrow, mid day:
                        fcdatetime = datetime.combine(datetime.today(),
                                                      time(12))
                        # add daycnt days
                        fcdatetime += timedelta(days=daycnt)
                        # add timezoneoffset, to show OK in HA gui
                        fcdatetime -= timedelta(seconds=local_time_offset())

                        fcdata = {ATTR_TEMPERATURE: get_temp(tmpsect),
                                  CONF_DATETIME: fcdatetime}
                        self.data[CONF_FORECAST].append(fcdata)
        _LOGGER.debug('BR Forecast data: %s', self.forecast)

        yield from self.update_devices()

    @property
    def stationname(self):
        """Return the name of the selected weatherstation."""
        if CONF_STATIONNAME in self.data:
            return self.data[CONF_STATIONNAME]

    @property
    def condition(self):
        """Return the condition."""
        if CONF_SYMBOL in self.data:
            return self.data[CONF_SYMBOL]

    @property
    def temperature(self):
        """Return the temperature, or None."""
        if ATTR_TEMPERATURE in self.data:
            try:
                return float(self.data[ATTR_TEMPERATURE])
            except (ValueError, TypeError):
                return None

    @property
    def pressure(self):
        """Return the pressure, or None."""
        if CONF_PRESSURE in self.data:
            try:
                return float(self.data[CONF_PRESSURE])
            except (ValueError, TypeError):
                return None

    @property
    def humidity(self):
        """Return the humidity, or None."""
        if CONF_HUMIDITY in self.data:
            try:
                return int(self.data[CONF_HUMIDITY])
            except (ValueError, TypeError):
                return None

    @property
    def wind_speed(self):
        """Return the windspeed, or None."""
        if CONF_WINDSPEED in self.data:
            try:
                return float(self.data[CONF_WINDSPEED])
            except (ValueError, TypeError):
                return None

    @property
    def wind_bearing(self):
        """Return the wind bearing, or None."""
        if CONF_WINDDIRECTION in self.data:
            try:
                return int(self.data[CONF_WINDDIRECTION])
            except (ValueError, TypeError):
                return None

    @property
    def forecast(self):
        """Return the forecast data."""
        if CONF_FORECAST in self.data:
            return self.data[CONF_FORECAST]
