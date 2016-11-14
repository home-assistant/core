# ------------------------------------------------------------------------
# coding=utf-8
#
#  Created by Martin J. Laubach on 2016-11-07
# ------------------------------------------------------------------------

"""
Sensor for data from Austrian "Zentralanstalt für Meteorologie und Geodynamik".

This is a sensor for the Austrian weather service "Zentralanstalt für
Meteorologie und Geodynamik" (aka ZAMG).

The configuration should look like this:

    - platform: zamg
      station_id: 11035
      monitored_conditions:
        - temperature
        - humidity
        - pressure
        - wind_speed
        - precipitation

Recognised conditions are:

    pressure (Pressure at station level)
    pressure_sealevel (Pressure at Sea Level)
    humidity (Humidity)
    wind_speed (Wind Speed)
    wind_bearing (Wind Bearing)
    wind_max_speed (Top Wind Speed)
    wind_max_bearing (Top Wind Bearing)
    sun_last_hour (Sun Last Hour Percentage)
    temperature (Temperature)
    precipitation (Precipitation)
    dewpoint (Dew Point)

The following stations are available:

    11010   Linz/Hörsching
    11012   Kremsmünster
    11022   Retz
    11035   Wien/Hohe Warte
    11036   Wien/Schwechat
    11101   Bregenz
    11121   Innsbruck
    11126   Patscherkofel
    11130   Kufstein
    11150   Salzburg
    11155   Feuerkogel
    11157   Aigen im Ennstal
    11171   Mariazell
    11190   Eisenstadt
    11204   Lienz
"""

import csv
from datetime import timedelta
import logging
import requests

import voluptuous as vol

from homeassistant.components.weather import (
    WeatherEntity, PLATFORM_SCHEMA, ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING, ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_ATTRIBUTION
)
from homeassistant.const import (
    TEMP_CELSIUS, CONF_MONITORED_CONDITIONS,
    CONF_NAME, STATE_UNKNOWN
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'zamg'
ATTRIBUTION = 'Data provided by ZAMG'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)  # Only updates once per hour

CONF_STATION_ID = "station_id"

SENSOR_TYPES = {
    ATTR_WEATHER_PRESSURE: ('Pressure', 'hPa', 'LDstat hPa', float),
    'pressure_sealevel': ('Pressure at Sea Level', 'hPa', 'LDred hPa', float),
    ATTR_WEATHER_HUMIDITY: ('Humidity', '%', 'RF %', int),
    ATTR_WEATHER_WIND_SPEED: ('Wind Speed', 'km/h', 'WG km/h', float),
    ATTR_WEATHER_WIND_BEARING: ('Wind Bearing', '°', 'WR °', int),
    'wind_max_speed': ('Top Wind Speed', 'km/h', 'WSG km/h', float),
    'wind_max_bearing': ('Top Wind Bearing', '°', 'WSR °', int),
    'sun_last_hour': ('Sun Last Hour', '%', 'SO %', int),
    ATTR_WEATHER_TEMPERATURE: ('Temperature', '°C', 'T °C', float),
    'precipitation': ('Precipitation', 'l/m²', 'N l/m²', int),
    'dewpoint': ('Dew Point', '°C', 'TP °C', float),
    # The following probably not useful for general consumption,
    # but we need them to fill in internal attributes
    'station_name': ('Station Name', None, 'Name', str),
    'station_elevation': ('Station Elevation', 'm', 'Höhe m', int),
    'update_date': ('Update Date', None, 'Datum', str),
    'update_time': ('Update Time', None, 'Zeit', str),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


# ------------------------------------------------------------------------
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup platform."""
    station_id = config.get(CONF_STATION_ID)
    name = config.get(CONF_NAME)

    probe = ZamgData(station_id=station_id, logger=_LOGGER)

    sensors = [ZAMGWeather(probe, variable, name)
               for variable in config[CONF_MONITORED_CONDITIONS]]

    add_devices(sensors, True)


# ------------------------------------------------------------------------
class ZAMGWeather(WeatherEntity):
    """
    I am a weather wrapper for a specific station and a specific attribute.

    Multiple instances (one for each condition) will refer to the same
    probe, so things will only get fetched once.
    """

    attribution = ATTRIBUTION
    temperature_unit = TEMP_CELSIUS

    def __init__(self, probe, variable, name):
        """Init condition sensor."""
        self.probe = probe
        self.client_name = name
        self.variable = variable

    def update(self):
        """Delegate update to probe."""
        self.probe.update()

    @property
    def name(self):
        """Build name."""
        return "%s_%s" % (self.client_name, self.variable)

    @property
    def state(self):
        """Return state."""
        return self.probe.get_data(self.variable)

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_WEATHER_ATTRIBUTION: self.attribution,
            "friendly_name": SENSOR_TYPES[self.variable][0],
            "station": self.probe.get_data('station_name'),
            "updated": "%s %s" % (self.probe.get_data('update_date'),
                                  self.probe.get_data('update_time'))

        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self.variable][1]

    @property
    def condition(self):
        """Return unknown, we only do raw weather data, no condition."""
        return STATE_UNKNOWN

    @property
    def humidity(self):
        """Return humidity."""
        return self.probe.get_data(ATTR_WEATHER_HUMIDITY)

    @property
    def temperature(self):
        """Return temperature."""
        return self.probe.get_data(ATTR_WEATHER_TEMPERATURE)


# ------------------------------------------------------------------------
class ZamgData(object):
    """
    I represent weather data for a specific site.

    From the web site:

    Sie beinhalten neben Stationsnummer, Stationsname, Seehöhe der Station,
    Messdatum und Messzeit (Lokalzeit) die meteorologischen Messwerte von
    Temperatur, Taupunkt, relative Luftfeuchtigkeit, Richtung und
    Geschwindigkeit des Windmittels und der Windspitze, Niederschlagssumme
    der letzten Stunde, Luftdruck reduziert auf Meeresniveau und Luftdruck
    auf Stationsniveau sowie die Sonnenscheindauer der letzten Stunde (in
    Prozent). Die Messstationen, die diese Daten liefern, sind über das
    Bundesgebiet verteilt und beinhalten alle Landeshauptstädte sowie
    die wichtigsten Bergstationen.
    """

    API_URL = "http://www.zamg.ac.at/ogd/"

    API_FIELDS = {
        v[2]: (k, v[3])
        for k, v in SENSOR_TYPES.items()
    }

    def __init__(self, logger, station_id):
        """Initialize the probe."""
        self._logger = logger
        self._station_id = station_id
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """
        Update data set.

        Fetch a new data set from the zamg server, parse it and
        update internal state accordingly
        """
        response = requests.get(self.API_URL)
        response.encoding = 'UTF8'
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'whatever')
            if content_type == 'text/csv':
                content = response.text
                data = (line for line in content.split('\n'))
                reader = csv.DictReader(data, delimiter=';', quotechar='"')
                for row in reader:
                    if row.get("Station", None) == self._station_id:
                        self.data = {
                            self.API_FIELDS.get(k)[0]:
                                self.API_FIELDS.get(k)[1](v.replace(',', '.'))
                            for k, v in row.items()
                            if v and k in self.API_FIELDS
                        }
                        break
            else:
                self._logger.error("Expected text/csv but got %s",
                                   content_type)
        else:
            self._logger.error("API call returned with status %s",
                               response.status_code)

    def get_data(self, variable):
        """Generic accessor for data."""
        return self.data.get(variable, STATE_UNKNOWN)

# ------------------------------------------------------------------------
