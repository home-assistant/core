"""The tests for the NOAA/NWS weather sensor component."""

import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT,
                                 LENGTH_KILOMETERS, LENGTH_MILES,
                                 LENGTH_INCHES)
from homeassistant.util.unit_system import (IMPERIAL_SYSTEM)

from tests.common import (get_test_home_assistant)

VALID_CONFIG_MINIMAL = {
    'sensor': {
        'platform': 'noaaweather',
        'monitored_conditions': ['temperature'],
    }
}

VALID_CONFIG_FULL = {
    'sensor': {
        'platform': 'noaaweather',
        'monitored_conditions': [
            'temperature',
            'textDescription',
            'dewpoint',
            'windChill',
            'windSpeed',
            'windDirection',
            'windGust',
            'barometricPressure',
            'seaLevelPressure',
            'precipitationLastHour',
            'precipitationLast3Hours',
            'precipitationLast6Hours',
            'relativeHumidity',
            'heatIndex',
            'visibility',
            'cloudLayers',
        ],
    }
}

BAD_CONF_LOCATION = {
    'sensor': {
        'platform': 'noaaweather',
        'latitude': 0,
        'longitude': 0,
        'monitored_conditions': [
            'temperature',
        ],
    }
}

BAD_CONF_STATION = {
    'sensor': {
        'platform': 'noaaweather',
        'stationcode': 'KLGA',
        'monitored_conditions': [
            'temperature',
        ],
    }
}

STATION_LIST = ['KJFK', 'KLGA', 'KNYC']

OBSERVATION_DATA = [{
    "@id": "https://api.weather.gov/stations/"
           "KJFK/observations/2019-03-24T22:51:00+00:00",
    "@type": "wx:ObservationStation",
    "elevation": {
        "value": 7,
        "unitCode": "unit:m"
    },
    "station": "https://api.weather.gov/stations/KJFK",
    "timestamp": "2019-03-24T22:51:00+00:00",
    "rawMessage": "KJFK 242151Z 20009KT 10SM FEW150 OVC250 12/02 A3003 "
                  "RMK AO2 SLP168 T01170017",
    "textDescription": "Cloudy",
    "icon": "https://api.weather.gov/icons/land/day/ovc?size=medium",
    "presentWeather": [],
    "temperature": {
        "value": 11.700000000000045,
        "unitCode": "unit:degC",
        "qualityControl": "qc:V"
    },
    "dewpoint": {
        "value": -1.5,
        "unitCode": "unit:degC",
        "qualityControl": "qc:Z"
    },
    "windDirection": {
        "value": 200,
        "unitCode": "unit:degree_(angle)",
        "qualityControl": "qc:V"
    },
    "windSpeed": {
        "value": 4.6,
        "unitCode": "unit:m_s-1",
        "qualityControl": "qc:V"
    },
    "windGust": {
        "value": 9.3,
        "unitCode": "unit:m_s-1",
        "qualityControl": "qc:Z"
    },
    "barometricPressure": {
        "value": 101690,
        "unitCode": "unit:Pa",
        "qualityControl": "qc:V"
    },
    "seaLevelPressure": {
        "value": 101680,
        "unitCode": "unit:Pa",
        "qualityControl": "qc:V"
    },
    "visibility": {
        "value": 16090,
        "unitCode": "unit:m",
        "qualityControl": "qc:C"
    },
    "maxTemperatureLast24Hours": {
        "value": None,
        "unitCode": "unit:degC",
        "qualityControl": None
    },
    "minTemperatureLast24Hours": {
        "value": None,
        "unitCode": "unit:degC",
        "qualityControl": None
    },
    "precipitationLastHour": {
        "value": 0.010,
        "unitCode": "unit:m",
        "qualityControl": "qc:Z"
    },
    "precipitationLast3Hours": {
        "value": 0.011,
        "unitCode": "unit:m",
        "qualityControl": "qc:Z"
    },
    "precipitationLast6Hours": {
        "value": 0.015,
        "unitCode": "unit:m",
        "qualityControl": "qc:Z"
    },
    "relativeHumidity": {
        "value": 65,
        "unitCode": "unit:percent",
        "qualityControl": "qc:C"
    },
    "windChill": {
        "value": 4.4,
        "unitCode": "unit:degC",
        "qualityControl": "qc:V"
    },
    "heatIndex": {
        "value": 11.1,
        "unitCode": "unit:degC",
        "qualityControl": "qc:V"
    },
    "cloudLayers": [
        {
            "base": {
                "value": 4570,
                "unitCode": "unit:m"
            },
            "amount": "FEW"
        },
        {
            "base": {
                "value": 7620,
                "unitCode": "unit:m"
            },
            "amount": "OVC"
        }
    ]
}
]


async def get_obs_station_list_mock(nws):
    """Return station list based on location.

    If the latitude and longitude are both zero, return an empty
    list.  Otherwise return our sample list.
    """
    print(nws.latlon)
    latitude, longitude = nws.latlon
    if latitude == 0 and longitude == 0:
        return None
    return STATION_LIST


async def get_obs_for_station_mock(nws, errorstate):
    """Return static example of observation data.

    If the station is KJFK, we return the sample observation data.
    If not, we will return None, which is what happens when there
    is no observation data available.
    """
    if nws.station == "KJFK":
        return OBSERVATION_DATA
    return None


class TestWeather(unittest.TestCase):
    """Test the NOAA/NWS weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.noaaweather.sensor.get_obs_station_list',
           new=get_obs_station_list_mock)
    @patch('homeassistant.components.noaaweather.sensor.get_obs_for_station',
           new=get_obs_for_station_mock)
    def test_setup_minimal(self):
        """Test for minimal weather sensor config.

        This test case is with default (metric) units.
        """
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.noaa_weather_temperature')
        assert state is not None

        assert state.state == '11.7'
        assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Temperature"

    @patch('homeassistant.components.noaaweather.sensor.get_obs_station_list',
           new=get_obs_station_list_mock)
    @patch('homeassistant.components.noaaweather.sensor.get_obs_for_station',
           new=get_obs_for_station_mock)
    def test_setup_minimal_imperial(self):
        """Test for minimal weather sensor config.

        This case is with imperial units.
        """
        self.hass.config.units = IMPERIAL_SYSTEM
        assert setup_component(self.hass, 'sensor',
                               VALID_CONFIG_MINIMAL)

        state = self.hass.states.get('sensor.noaa_weather_temperature')
        assert state is not None

        assert state.state == '53.1'
        assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Temperature"

    @patch('homeassistant.components.noaaweather.sensor.get_obs_station_list',
           new=get_obs_station_list_mock)
    @patch('homeassistant.components.noaaweather.sensor.get_obs_for_station',
           new=get_obs_for_station_mock)
    def test_setup_badconflocation(self):
        """Test for configuration with bad location."""
        assert setup_component(self.hass, 'sensor', BAD_CONF_LOCATION)

        state = self.hass.states.get('sensor.noaa_weather_temperature')
        assert state is None

    @patch('homeassistant.components.noaaweather.sensor.get_obs_station_list',
           new=get_obs_station_list_mock)
    @patch('homeassistant.components.noaaweather.sensor.get_obs_for_station',
           new=get_obs_for_station_mock)
    def test_setup_badconfstation(self):
        """Test for configuration with bad station."""
        assert setup_component(self.hass, 'sensor', BAD_CONF_STATION)

        state = self.hass.states.get('sensor.noaa_weather_temperature')
        assert state is None

    @patch('homeassistant.components.noaaweather.sensor.get_obs_station_list',
           new=get_obs_station_list_mock)
    @patch('homeassistant.components.noaaweather.sensor.get_obs_for_station',
           new=get_obs_for_station_mock)
    def test_setup_full(self):
        """Test for full weather sensor config.

        This test case is with default (metric) units.
        """
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_FULL)

        state = self.hass.states.get('sensor.noaa_weather_temperature')
        assert state is not None

        assert state.state == '11.7'
        assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Temperature"

        state = self.hass.states.get('sensor.noaa_weather_weather')
        assert state is not None

        assert state.state == 'Cloudy'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Weather"

        state = self.hass.states.get('sensor.noaa_weather_dewpoint')
        assert state is not None

        assert state.state == '-1.5'
        assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather dewpoint"

        state = self.hass.states.get('sensor.noaa_weather_wind_chill')
        assert state is not None

        assert state.state == '4.4'
        assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Chill"

        state = self.hass.states.get('sensor.noaa_weather_heat_index')
        assert state is not None

        assert state.state == '11.1'
        assert state.attributes.get('unit_of_measurement') == TEMP_CELSIUS
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Heat Index"

        state = self.hass.states.get('sensor.noaa_weather_wind_speed')
        assert state is not None

        assert state.state == '16.6'
        assert state.attributes.get('unit_of_measurement') == 'km/h'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Speed"

        state = self.hass.states.get('sensor.noaa_weather_wind_bearing')
        assert state is not None

        assert state.state == '200'
        assert state.attributes.get('unit_of_measurement') == '°'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Bearing"

        state = self.hass.states.get('sensor.noaa_weather_wind_gust')
        assert state is not None

        assert state.state == '33.5'
        assert state.attributes.get('unit_of_measurement') == 'km/h'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Gust"

        state = self.hass.states.get('sensor.noaa_weather_pressure')
        assert state is not None

        assert state.state == '1016.9'
        assert state.attributes.get('unit_of_measurement') == 'mbar'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Pressure"

        state = self.hass.states.get('sensor.noaa_weather_sea_level_pressure')
        assert state is not None

        assert state.state == '1016.8'
        assert state.attributes.get('unit_of_measurement') == 'mbar'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Sea Level Pressure"

        state = self.hass.states.get(
            'sensor.noaa_weather_precipitation_in_last_hour')
        assert state is not None

        assert state.state == '10.0'
        assert state.attributes.get('unit_of_measurement') == 'mm'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Precipitation in last hour"

        state = self.hass.states.get(
            'sensor.noaa_weather_precipitation_in_last_3_hours')
        assert state is not None

        assert state.state == '11.0'
        assert state.attributes.get('unit_of_measurement') == 'mm'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Precipitation in last 3 hours"

        state = self.hass.states.get(
            'sensor.noaa_weather_precipitation_in_last_6_hours')
        assert state is not None

        assert state.state == '15.0'
        assert state.attributes.get('unit_of_measurement') == 'mm'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Precipitation in last 6 hours"

        state = self.hass.states.get('sensor.noaa_weather_humidity')
        assert state is not None

        assert state.state == '65'
        assert state.attributes.get('unit_of_measurement') == '%'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Humidity"

        state = self.hass.states.get('sensor.noaa_weather_visibility')
        assert state is not None

        assert state.state == '16.1'
        assert state.attributes.get('unit_of_measurement') == \
            LENGTH_KILOMETERS
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Visibility"

        state = self.hass.states.get('sensor.noaa_weather_cloud_layers')
        assert state is not None

        assert state.state == 'FEW'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Cloud Layers"

    @patch('homeassistant.components.noaaweather.sensor.get_obs_station_list',
           new=get_obs_station_list_mock)
    @patch('homeassistant.components.noaaweather.sensor.get_obs_for_station',
           new=get_obs_for_station_mock)
    def test_setup_full_imperial(self):
        """Test for full weather sensor config.

        This test case is with imperial units.
        """
        self.hass.config.units = IMPERIAL_SYSTEM
        assert setup_component(self.hass, 'sensor', VALID_CONFIG_FULL)

        state = self.hass.states.get('sensor.noaa_weather_temperature')
        assert state is not None

        assert state.state == '53.1'
        assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Temperature"

        state = self.hass.states.get('sensor.noaa_weather_weather')
        assert state is not None

        assert state.state == 'Cloudy'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Weather"

        state = self.hass.states.get('sensor.noaa_weather_dewpoint')
        assert state is not None

        assert state.state == '29.3'
        assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather dewpoint"

        state = self.hass.states.get('sensor.noaa_weather_wind_chill')
        assert state is not None

        assert state.state == '39.9'
        assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Chill"

        state = self.hass.states.get('sensor.noaa_weather_heat_index')
        assert state is not None

        assert state.state == '52.0'
        assert state.attributes.get('unit_of_measurement') == TEMP_FAHRENHEIT
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Heat Index"

        state = self.hass.states.get('sensor.noaa_weather_wind_speed')
        assert state is not None

        assert state.state == '10.3'
        assert state.attributes.get('unit_of_measurement') == 'mph'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Speed"

        state = self.hass.states.get('sensor.noaa_weather_wind_bearing')
        assert state is not None

        assert state.state == '200'
        assert state.attributes.get('unit_of_measurement') == '°'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Bearing"

        state = self.hass.states.get('sensor.noaa_weather_wind_gust')
        assert state is not None

        assert state.state == '20.8'
        assert state.attributes.get('unit_of_measurement') == 'mph'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Wind Gust"

        state = self.hass.states.get('sensor.noaa_weather_pressure')
        assert state is not None

        assert state.state == '1016.9'
        assert state.attributes.get('unit_of_measurement') == 'mbar'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Pressure"

        state = self.hass.states.get('sensor.noaa_weather_sea_level_pressure')
        assert state is not None

        assert state.state == '1016.8'
        assert state.attributes.get('unit_of_measurement') == 'mbar'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Sea Level Pressure"

        state = self.hass.states.get(
            'sensor.noaa_weather_precipitation_in_last_hour')
        assert state is not None

        assert state.state == '0.4'
        assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Precipitation in last hour"

        state = self.hass.states.get(
            'sensor.noaa_weather_precipitation_in_last_3_hours')
        assert state is not None

        assert state.state == '0.4'
        assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Precipitation in last 3 hours"

        state = self.hass.states.get(
            'sensor.noaa_weather_precipitation_in_last_6_hours')
        assert state is not None

        assert state.state == '0.6'
        assert state.attributes.get('unit_of_measurement') == LENGTH_INCHES
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Precipitation in last 6 hours"

        state = self.hass.states.get('sensor.noaa_weather_humidity')
        assert state is not None

        assert state.state == '65'
        assert state.attributes.get('unit_of_measurement') == '%'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Humidity"

        state = self.hass.states.get('sensor.noaa_weather_visibility')
        assert state is not None

        assert state.state == '10.0'
        assert state.attributes.get('unit_of_measurement') == LENGTH_MILES
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Visibility"

        state = self.hass.states.get('sensor.noaa_weather_cloud_layers')
        assert state is not None

        assert state.state == 'FEW'
        assert state.attributes.get('friendly_name') == \
            "NOAA Weather Cloud Layers"
