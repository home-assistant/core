"""
Support for magicseaweed data from magicseaweed.com.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.magicseaweed/
"""
from datetime import timedelta, datetime
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_HOURS = 'hours'
CONF_SPOT_ID = 'spot_id'
CONF_UNITS = 'units'
CONF_UPDATE_INTERVAL = 'update_interval'

DEFAULT_UNIT = 'us'
DEFAULT_NAME = 'MSW'
DEFAULT_ATTRIBUTION = "Data provided by magicseaweed.com"

ICON = 'mdi:waves'

API_URL = 'http://magicseaweed.com/api/{}/forecast/'

HOURS = ['12AM', '3AM', '6AM', '9AM', '12PM', '3PM', '6PM', '9PM']

SENSOR_TYPES = {
    'max_breaking_swell': ['Max'],
    'min_breaking_swell': ['Min'],
    'swell_forecast': ['Forecast'],
}

UNITS = ['eu', 'uk', 'us']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_SPOT_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_HOURS, default=None):
        vol.All(cv.ensure_list, [vol.In(HOURS)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNITS): vol.In(UNITS),
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=300)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})


# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Magicseaweed sensor."""
    name = config.get(CONF_NAME)
    spot_id = config[CONF_SPOT_ID]
    api_key = config[CONF_API_KEY]
    hours = config.get(CONF_HOURS)

    if CONF_UNITS in config:
        units = config.get(CONF_UNITS)
    elif hass.config.units.is_metric:
        units = UNITS[0]
    else:
        units = UNITS[2]

    forecast_data = MagicSeaweedData(
        api_key=api_key,
        spot_id=spot_id,
        units=units,
        interval=config.get(CONF_UPDATE_INTERVAL))
    forecast_data.update()

    # If connection failed don't setup platform.
    if forecast_data.currently is None or forecast_data.hourly is None:
        return False

    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        if 'forecast' in variable:
            sensors.append(MagicSeaweedSensor(forecast_data, variable, name,
                                              units))

        else:
            sensors.append(MagicSeaweedSensor(forecast_data, variable, name,
                                              units))
            if hours is not None:
                for hour in hours:
                    sensors.append(MagicSeaweedSensor(
                        forecast_data, variable, name, units, hour))
    add_devices(sensors, True)


class MagicSeaweedSensor(Entity):
    """Implementation of a MagicSeaweed sensor."""

    def __init__(self, forecast_data, sensor_type, name, unit_system,
                 hour=None):
        """Initialize the sensor."""
        self.client_name = name
        self.data = forecast_data
        self.hour = hour
        self.type = sensor_type
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._name = SENSOR_TYPES[sensor_type][0]
        self._icon = None
        self._state = None
        self._unit_system = unit_system
        self._unit_of_measurement = None

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.hour is None and 'forecast' in self.type:
            return "{} {}".format(self.client_name, self._name)
        elif self.hour is None:
            return "Current {} {}".format(self.client_name, self._name)
        return "{} {} {}".format(
            self.hour, self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self._unit_system

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the entity weather icon, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    def update(self):
        """Get the latest data from Magicseaweed and updates the states."""
        self.data.update()
        if self.hour is None:
            forecast = self.data.currently
        else:
            forecast = self.data.hourly[self.hour]

        occurs = dt_util.utc_from_timestamp(
            forecast.get('localTimestamp')).strftime("%a %-I %p")
        utc_issue = dt_util.utc_from_timestamp(
            forecast.get('issueTimestamp')).strftime("%a %-I %p")
        swell = forecast.get('swell')
        wind = forecast.get('wind', None)
        condition = forecast.get('condition', None)
        rating = "{} stars, {} faded".format(
            forecast.get('solidRating') + forecast.get('fadedRating'),
            forecast.get('solidRating'))

        self._unit_of_measurement = swell.get('unit', None)
        if self.type == 'min_breaking_swell':
            self._state = swell.get('minBreakingHeight')
        elif self.type == 'max_breaking_swell':
            self._state = swell.get('maxBreakingHeight')
        elif self.type == 'swell_forecast':
            summary = "{} - {}".format(
                swell.get('minBreakingHeight'),
                swell.get('maxBreakingHeight'))
            self._state = summary
            if self.hour is None:
                for hour, data in self.data.hourly.items():
                    occurs = hour
                    hr_swell = data.get('swell')
                    hr_summary = "{} - {} {}".format(
                        hr_swell.get('minBreakingHeight'),
                        hr_swell.get('maxBreakingHeight'),
                        hr_swell.get('unit'))
                    self._attrs[occurs] = hr_summary

        if self.type != 'swell_forecast':
            self._attrs.update({
                'air_pressure': "{}{}".format(condition.get('pressure'),
                                              condition.get('unitPressure')),
                'air_temp': "{}° {}".format(condition.get('temperature'),
                                            condition.get('unit')),
                'rating': rating,
                'begins': occurs,
                'issued': utc_issue,
                'max_breaking_height': swell.get('maxBreakingHeight'),
                'min_breaking_height': swell.get('minBreakingHeight'),
                'probability': "{}%".format(swell.get('probability')),
                'swell_period': "{} seconds".format(
                    swell.get('components', {})
                    .get('combined', {})
                    .get('period', {})),
                'wind_chill': "{}°".format(wind.get('chill')),
                'wind_direction': "{}° {}".format(
                    wind.get('direction'),
                    wind.get('compassDirection')),
                'wind_gusts': "{} {}".format(wind.get('gusts'),
                                             wind.get('unit')),
                'wind_speed': "{} {}".format(wind.get('speed'),
                                             wind.get('unit')),
            })


class MagicSeaweedData(object):
    """Get the latest data from MagicSeaweed."""

    def __init__(self, api_key, spot_id, units, interval):
        """Initialize the data object."""
        self._api_key = api_key
        self._spot_id = spot_id
        self.currently = None
        self.hourly = {}
        self.params = {'spot_id': self._spot_id,
                       'units': units}

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Get the latest data from MagicSeaweed."""
        try:
            now = datetime.now()
            plus_24 = now + timedelta(hours=24)
            self.params['start'] = now.timestamp()
            self.params['end'] = plus_24.timestamp()
            response = requests.get(API_URL.format(self._api_key),
                                    params=self.params, timeout=5)
            data = response.json()
            self.currently = data[0]
            for forecast in data:
                hour = datetime.utcfromtimestamp(
                    forecast.get('localTimestamp')).strftime("%-I%p")
                self.hourly[hour] = forecast

        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from %s", API_URL)
            data = None
