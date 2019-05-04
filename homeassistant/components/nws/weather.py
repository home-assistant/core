"""Support for NWS weather service."""
from collections import OrderedDict
from datetime import timedelta
import logging
from statistics import mean

import async_timeout
import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_SPEED, ATTR_FORECAST_WIND_BEARING)
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE,
    LENGTH_KILOMETERS, LENGTH_METERS, LENGTH_MILES, PRESSURE_HPA, PRESSURE_PA,
    PRESSURE_INHG, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature

REQUIREMENTS = ['pynws==0.6']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = 'Data from National Weather Service/NOAA'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

CONF_STATION = 'station'

ATTR_FORECAST_DETAIL_DESCRIPTION = 'detailed_description'
ATTR_FORECAST_PRECIP_PROB = 'precipitation_probability'
ATTR_FORECAST_DAYTIME = 'daytime'

# Ordered so that a single condition can be chosen from multiple weather codes.
# Known NWS conditions that do not map: cold
CONDITION_CLASSES = OrderedDict([
    ('snowy', ['snow', 'snow_sleet', 'sleet', 'blizzard']),
    ('snowy-rainy', ['rain_snow', 'rain_sleet', 'fzra',
                     'rain_fzra', 'snow_fzra']),
    ('hail', []),
    ('lightning-rainy', ['tsra', 'tsra_sct', 'tsra_hi']),
    ('lightning', []),
    ('pouring', []),
    ('rainy', ['rain', 'rain_showers', 'rain_showers_hi']),
    ('windy-variant', ['wind_bkn', 'wind_ovc']),
    ('windy', ['wind_skc', 'wind_few', 'wind_sct']),
    ('fog', ['fog']),
    ('clear', ['skc']),  # sunny and clear-night
    ('cloudy', ['bkn', 'ovc']),
    ('partlycloudy', ['few', 'sct'])
])

FORECAST_CLASSES = {
    ATTR_FORECAST_DETAIL_DESCRIPTION: 'detailedForecast',
    ATTR_FORECAST_TEMP: 'temperature',
    ATTR_FORECAST_TIME: 'startTime',
}

FORECAST_MODE = ['daynight', 'hourly']

WIND_DIRECTIONS = ['N', 'NNE', 'NE', 'ENE',
                   'E', 'ESE', 'SE', 'SSE',
                   'S', 'SSW', 'SW', 'WSW',
                   'W', 'WNW', 'NW', 'NNW']

WIND = {name: idx * 360 / 16 for idx, name in enumerate(WIND_DIRECTIONS)}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_MODE, default='daynight'): vol.In(FORECAST_MODE),
    vol.Optional(CONF_STATION): cv.string,
    vol.Required(CONF_API_KEY): cv.string
})


def parse_icon(icon):
    """
    Parse icon url to NWS weather codes.

    Example:
    https://api.weather.gov/icons/land/day/skc/tsra,40?size=medium

    Example return:
    ('day', (('skc', 0), ('tsra', 40),))
    """
    icon_list = icon.split('/')
    time = icon_list[5]
    weather = [i.split('?')[0] for i in icon_list[6:]]
    code = [w.split(',')[0] for w in weather]
    chance = [int(w.split(',')[1]) if len(w.split(',')) == 2 else 0
              for w in weather]
    return time, tuple(zip(code, chance))


def convert_condition(time, weather):
    """
    Convert NWS codes to HA condition.

    Choose first condition in CONDITION_CLASSES that exists in weather code.
    If no match is found, return fitst condition from NWS
    """
    conditions = [w[0] for w in weather]
    prec_prob = [w[1] for w in weather]

    # Choose condition with highest priority.
    cond = next((key for key, value in CONDITION_CLASSES.items()
                 if any(condition in value for condition in conditions)),
                conditions[0])

    if cond == 'clear':
        if time == 'day':
            return 'sunny', max(prec_prob)
        if time == 'night':
            return 'clear-night', max(prec_prob)
    return cond, max(prec_prob)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the NWS weather platform."""
    from pynws import Nws

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    station = config.get(CONF_STATION)
    api_key = config[CONF_API_KEY]

    if None in (latitude, longitude):
        _LOGGER.error("Latitude/longitude not set in Home Assistant config")
        return

    websession = async_get_clientsession(hass)
    # ID request as being from HA, pynws prepends the api_key in addition
    api_key_ha = '{} {}'.format(api_key, 'homeassistant')
    nws = Nws(websession, latlon=(float(latitude), float(longitude)),
              userid=api_key_ha)

    _LOGGER.debug("Setting up station: %s", station)
    if station is None:
        with async_timeout.timeout(10, loop=hass.loop):
            stations = await nws.stations()
        _LOGGER.debug("Station list: %s", stations)
        nws.station = stations[0]
        _LOGGER.debug("Initialized for coordinates %s, %s -> station %s",
                      latitude, longitude, stations[0])
    else:
        nws.station = station
        _LOGGER.debug("Initialized station %s", station[0])

    async_add_entities([NWSWeather(nws, hass.config.units, config)], True)


class NWSWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, nws, units, config):
        """Initialise the platform with a data instance and station name."""
        self._nws = nws
        self._station_name = config.get(CONF_NAME, self._nws.station)
        self._observation = None
        self._forecast = None
        self._description = None
        self._is_metric = units.is_metric
        self._mode = config[CONF_MODE]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update Condition."""
        with async_timeout.timeout(10, loop=self.hass.loop):
            _LOGGER.debug("Updating station observations %s",
                          self._nws.station)
            self._observation = await self._nws.observations()
            _LOGGER.debug("Updating forecast")
            if self._mode == 'daynight':
                self._forecast = await self._nws.forecast()
            elif self._mode == 'hourly':
                self._forecast = await self._nws.forecast_hourly()
        _LOGGER.debug("Observations: %s", self._observation)
        _LOGGER.debug("Forecasts: %s", self._forecast)

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the station."""
        return self._station_name

    @property
    def temperature(self):
        """Return the current temperature."""
        temp_c = self._observation[0]['temperature']['value']
        if temp_c is not None:
            return convert_temperature(temp_c, TEMP_CELSIUS, TEMP_FAHRENHEIT)
        return None

    @property
    def pressure(self):
        """Return the current pressure."""
        pressure_pa = self._observation[0]['seaLevelPressure']['value']
        # convert Pa to in Hg
        if pressure_pa is None:
            return None

        if self._is_metric:
            pressure = convert_pressure(pressure_pa, PRESSURE_PA, PRESSURE_HPA)
            pressure = round(pressure)
        else:
            pressure = convert_pressure(pressure_pa,
                                        PRESSURE_PA, PRESSURE_INHG)
            pressure = round(pressure, 2)
        return pressure

    @property
    def humidity(self):
        """Return the name of the sensor."""
        return self._observation[0]['relativeHumidity']['value']

    @property
    def wind_speed(self):
        """Return the current windspeed."""
        wind_m_s = self._observation[0]['windSpeed']['value']
        if wind_m_s is None:
            return None
        wind_m_hr = wind_m_s * 3600

        if self._is_metric:
            wind = convert_distance(wind_m_hr,
                                    LENGTH_METERS, LENGTH_KILOMETERS)
        else:
            wind = convert_distance(wind_m_hr, LENGTH_METERS, LENGTH_MILES)
        return round(wind)

    @property
    def wind_bearing(self):
        """Return the current wind bearing (degrees)."""
        return self._observation[0]['windDirection']['value']

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def condition(self):
        """Return current condition."""
        time, weather = parse_icon(self._observation[0]['icon'])
        cond, _ = convert_condition(time, weather)
        return cond

    @property
    def visibility(self):
        """Return visibility."""
        vis_m = self._observation[0]['visibility']['value']
        if vis_m is None:
            return None

        if self._is_metric:
            vis = convert_distance(vis_m, LENGTH_METERS, LENGTH_KILOMETERS)
        else:
            vis = convert_distance(vis_m, LENGTH_METERS, LENGTH_MILES)
        return round(vis, 0)

    @property
    def forecast(self):
        """Return forecast."""
        forecast = []
        for forecast_entry in self._forecast:
            data = {attr: forecast_entry[name]
                    for attr, name in FORECAST_CLASSES.items()}
            if self._mode == 'daynight':
                data[ATTR_FORECAST_DAYTIME] = forecast_entry['isDaytime']
            time, weather = parse_icon(forecast_entry['icon'])
            cond, precip = convert_condition(time, weather)
            data[ATTR_FORECAST_CONDITION] = cond
            if precip > 0:
                data[ATTR_FORECAST_PRECIP_PROB] = precip
            else:
                data[ATTR_FORECAST_PRECIP_PROB] = None
            data[ATTR_FORECAST_WIND_BEARING] = \
                WIND[forecast_entry['windDirection']]

            # wind speed reported as '7 mph' or '7 to 10 mph'
            # if range, take average
            wind_speed = forecast_entry['windSpeed'].split(' ')[0::2]
            wind_speed_avg = mean(int(w) for w in wind_speed)
            if self._is_metric:
                data[ATTR_FORECAST_WIND_SPEED] = round(
                    convert_distance(wind_speed_avg,
                                     LENGTH_MILES, LENGTH_KILOMETERS))
            else:
                data[ATTR_FORECAST_WIND_SPEED] = round(wind_speed_avg)

            forecast.append(data)
        return forecast
