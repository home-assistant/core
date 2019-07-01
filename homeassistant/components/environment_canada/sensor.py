"""
Support for the Environment Canada weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.environment_canada/
"""
import datetime
import logging
import re

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, CONF_NAME, CONF_LATITUDE,
    CONF_LONGITUDE, ATTR_ATTRIBUTION, ATTR_LOCATION, ATTR_HIDDEN)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.util.dt as dt
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_UPDATED = 'updated'
ATTR_STATION = 'station'
ATTR_DETAIL = 'alert detail'
ATTR_TIME = 'alert time'

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = 'station'
CONF_LANGUAGE = 'language'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)

SENSOR_TYPES = {
    'temperature': {'english': 'Temperature',
                    'french': 'Température',
                    'unit': TEMP_CELSIUS},
    'dewpoint': {'english': 'Dew Point',
                 'french': 'Point de rosée',
                 'unit': TEMP_CELSIUS},
    'wind_chill': {'english': 'Wind Chill',
                   'french': 'Refroidissement éolien',
                   'unit': TEMP_CELSIUS},
    'humidex': {'english': 'Humidex',
                'french': 'Humidex',
                'unit': TEMP_CELSIUS},
    'pressure': {'english': 'Pressure',
                 'french': 'Pression',
                 'unit': 'kPa'},
    'tendency': {'english': 'Tendency',
                 'french': 'Tendance'},
    'humidity': {'english': 'Humidity',
                 'french': 'Humidité',
                 'unit': '%'},
    'visibility': {'english': 'Visibility',
                   'french': 'Visibilité',
                   'unit': 'km'},
    'condition': {'english': 'Condition',
                  'french': 'Condition'},
    'wind_speed': {'english': 'Wind Speed',
                   'french': 'Vitesse de vent',
                   'unit': 'km/h'},
    'wind_gust': {'english': 'Wind Gust',
                  'french': 'Rafale de vent',
                  'unit': 'km/h'},
    'wind_dir': {'english': 'Wind Direction',
                 'french': 'Direction de vent'},
    'high_temp': {'english': 'High Temperature',
                  'french': 'Haute température',
                  'unit': TEMP_CELSIUS},
    'low_temp': {'english': 'Low Temperature',
                 'french': 'Basse température',
                 'unit': TEMP_CELSIUS},
    'pop': {'english': 'Chance of Precip.',
            'french': 'Probabilité d\'averses',
            'unit': '%'},
    'forecast_period': {'english': 'Forecast Period',
                        'french': 'Période de prévision'},
    'text_summary': {'english': 'Text Summary',
                     'french': 'Résumé textuel'},
    'warnings': {'english': 'Warnings',
                 'french': 'Alertes'},
    'watches': {'english': 'Watches',
                'french': 'Veilles'},
    'advisories': {'english': 'Advisories',
                   'french': 'Avis'},
    'statements': {'english': 'Statements',
                   'french': 'Bulletins'},
    'endings': {'english': 'Ended',
                'french': 'Terminé'}
}


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    if not re.fullmatch(r'[A-Z]{2}/s0000\d{3}', station):
        raise vol.error.Invalid('Station ID must be of the form "XX/s0000###"')
    return station


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Inclusive(CONF_LATITUDE, 'latlon'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'latlon'): cv.longitude,
    vol.Optional(CONF_LANGUAGE, default='english'):
        vol.In(['english', 'french'])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Environment Canada sensor."""
    from env_canada import ECData

    if config.get(CONF_STATION):
        ec_data = ECData(station_id=config[CONF_STATION],
                         language=config.get(CONF_LANGUAGE))
    elif config.get(CONF_LATITUDE) and config.get(CONF_LONGITUDE):
        ec_data = ECData(coordinates=(config[CONF_LATITUDE],
                                      config[CONF_LONGITUDE]),
                         language=config.get(CONF_LANGUAGE))
    else:
        ec_data = ECData(coordinates=(hass.config.latitude,
                                      hass.config.longitude),
                         language=config.get(CONF_LANGUAGE))

    add_devices([ECSensor(sensor_type,
                          ec_data,
                          config.get(CONF_NAME),
                          config.get(CONF_LANGUAGE))
                 for sensor_type in config[CONF_MONITORED_CONDITIONS]],
                True)


class ECSensor(Entity):
    """Implementation of an Environment Canada sensor."""

    def __init__(self, sensor_type, ec_data, platform_name, language):
        """Initialize the sensor."""
        self.sensor_type = sensor_type
        self.ec_data = ec_data
        self.platform_name = platform_name
        self._state = None
        self._attr = None
        self.language = language

    @property
    def name(self):
        """Return the name of the sensor."""
        name = SENSOR_TYPES[self.sensor_type][self.language]
        if self.platform_name is None:
            return name
        return ' '.join([self.platform_name, name])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self.sensor_type].get('unit')

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update current conditions."""
        self.ec_data.update()
        self.ec_data.conditions.update(self.ec_data.alerts)

        self._attr = {}

        sensor_data = self.ec_data.conditions.get(self.sensor_type)
        if isinstance(sensor_data, list):
            self._state = ' | '.join([str(s.get('title'))
                                      for s in sensor_data])
            self._attr.update({
                ATTR_DETAIL: ' | '.join([str(s.get('detail'))
                                         for s in sensor_data]),
                ATTR_TIME: ' | '.join([str(s.get('date'))
                                       for s in sensor_data])
            })
        else:
            self._state = sensor_data

        timestamp = self.ec_data.conditions.get('timestamp')
        if timestamp:
            updated_utc = datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
            updated_local = dt.as_local(updated_utc).isoformat()
        else:
            updated_local = None

        hidden = bool(self._state is None or self._state == '')

        self._attr.update({
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_UPDATED: updated_local,
            ATTR_LOCATION: self.ec_data.conditions.get('location'),
            ATTR_STATION: self.ec_data.conditions.get('station'),
            ATTR_HIDDEN: hidden
        })
