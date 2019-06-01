"""Tests for the NWS weather component."""
import unittest
from unittest.mock import patch

import aiohttp

from homeassistant.components import weather
from homeassistant.components.nws.weather import ATTR_FORECAST_PRECIP_PROB
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY, ATTR_WEATHER_PRESSURE, ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY, ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED)
from homeassistant.components.weather import (
    ATTR_FORECAST, ATTR_FORECAST_CONDITION, ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME, ATTR_FORECAST_WIND_BEARING, ATTR_FORECAST_WIND_SPEED)

from homeassistant.const import (
    LENGTH_KILOMETERS, LENGTH_METERS, LENGTH_MILES, PRECISION_WHOLE,
    PRESSURE_INHG, PRESSURE_PA, PRESSURE_HPA, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.temperature import display_temp
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, MockDependency


OBS = [{
    'temperature': {'value': 7, 'qualityControl': 'qc:V'},
    'relativeHumidity': {'value': 10, 'qualityControl': 'qc:V'},
    'windChill': {'value': 10, 'qualityControl': 'qc:V'},
    'heatIndex': {'value': 10, 'qualityControl': 'qc:V'},
    'windDirection': {'value': 180, 'qualityControl': 'qc:V'},
    'visibility': {'value': 10000, 'qualityControl': 'qc:V'},
    'windSpeed': {'value': 10, 'qualityControl': 'qc:V'},
    'seaLevelPressure': {'value': 30000, 'qualityControl': 'qc:V'},
    'windGust': {'value': 10, 'qualityControl': 'qc:V'},
    'dewpoint': {'value': 10, 'qualityControl': 'qc:V'},
    'icon': 'https://api.weather.gov/icons/land/day/skc?size=medium',
    'textDescription': 'Sunny'
}]

METAR_MSG = ("PHNG 182257Z 06012KT 10SM FEW020 SCT026 SCT035 "
             "28/22 A3007 RMK AO2 SLP177 T02780217")

OBS_METAR = [{
    "rawMessage": METAR_MSG,
    "textDescription": "Partly Cloudy",
    "icon": "https://api.weather.gov/icons/land/day/sct?size=medium",
    "temperature": {"value": None, "qualityControl": "qc:Z"},
    "windDirection": {"value": None, "qualityControl": "qc:Z"},
    "windSpeed": {"value": None, "qualityControl": "qc:Z"},
    "seaLevelPressure": {"value": None, "qualityControl": "qc:Z"},
    "visibility": {"value": None, "qualityControl": "qc:Z"},
    "relativeHumidity": {"value": None, "qualityControl": "qc:Z"},
}]

OBS_NONE = [{
    "rawMessage": None,
    "textDescription": None,
    "icon": None,
    "temperature": {"value": None, "qualityControl": "qc:Z"},
    "windDirection": {"value": None, "qualityControl": "qc:Z"},
    "windSpeed": {"value": None, "qualityControl": "qc:Z"},
    "seaLevelPressure": {"value": None, "qualityControl": "qc:Z"},
    "visibility": {"value": None, "qualityControl": "qc:Z"},
    "relativeHumidity": {"value": None, "qualityControl": "qc:Z"},
}]


FORE = [{
    'endTime': '2018-12-21T18:00:00-05:00',
    'windSpeed': '8 to 10 mph',
    'windDirection': 'S',
    'shortForecast': 'Chance Showers And Thunderstorms',
    'isDaytime': True,
    'startTime': '2018-12-21T15:00:00-05:00',
    'temperatureTrend': None,
    'temperature': 41,
    'temperatureUnit': 'F',
    'detailedForecast': 'A detailed description',
    'name': 'This Afternoon',
    'number': 1,
    'icon': 'https://api.weather.gov/icons/land/day/skc/tsra,40?size=medium'
}]

HOURLY_FORE = [{
    'endTime': '2018-12-22T05:00:00-05:00',
    'windSpeed': '4 mph',
    'windDirection': 'N',
    'shortForecast': 'Chance Showers And Thunderstorms',
    'startTime': '2018-12-22T04:00:00-05:00',
    'temperatureTrend': None,
    'temperature': 32,
    'temperatureUnit': 'F',
    'detailedForecast': '',
    'number': 2,
    'icon': 'https://api.weather.gov/icons/land/night/skc?size=medium'
}]

STN = 'STNA'


class MockNws():
    """Mock Station from pynws."""

    def __init__(self, websession, latlon, userid):
        """Init mock nws."""
        pass

    async def observations(self, limit):
        """Mock Observation."""
        return OBS

    async def forecast(self):
        """Mock Forecast."""
        return FORE

    async def forecast_hourly(self):
        """Mock Hourly Forecast."""
        return HOURLY_FORE

    async def stations(self):
        """Mock stations."""
        return [STN]


class Prop:
    """Property data class for metar.  Initialize with desired return value."""

    def __init__(self, value_return):
        """Initialize with desired return."""
        self.value_return = value_return

    def value(self, units=''):
        """Return provided value."""
        return self.value_return


class MockMetar:
    """Mock Metar parser."""

    def __init__(self, code):
        """Set up mocked return values."""
        self.temp = Prop(27)
        self.press = Prop(1111)
        self.wind_speed = Prop(27)
        self.wind_dir = Prop(175)
        self.vis = Prop(5000)


class TestNWS(unittest.TestCase):
    """Test the NWS weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = IMPERIAL_SYSTEM
        self.lat = self.hass.config.latitude = 40.00
        self.lon = self.hass.config.longitude = -8.00

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_w_name(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

        state = self.hass.states.get('weather.homeweather')
        assert state.state == 'sunny'

        data = state.attributes
        temp_f = convert_temperature(7, TEMP_CELSIUS, TEMP_FAHRENHEIT)
        assert data.get(ATTR_WEATHER_TEMPERATURE) == \
            display_temp(self.hass, temp_f, TEMP_FAHRENHEIT, PRECISION_WHOLE)
        assert data.get(ATTR_WEATHER_HUMIDITY) == 10
        assert data.get(ATTR_WEATHER_PRESSURE) == round(
            convert_pressure(30000, PRESSURE_PA, PRESSURE_INHG), 2)
        assert data.get(ATTR_WEATHER_WIND_SPEED) == round(10 * 2.237)
        assert data.get(ATTR_WEATHER_WIND_BEARING) == 180
        assert data.get(ATTR_WEATHER_VISIBILITY) == round(
            convert_distance(10000, LENGTH_METERS, LENGTH_MILES))
        assert state.attributes.get('friendly_name') == 'HomeWeather'

        forecast = data.get(ATTR_FORECAST)
        assert forecast[0].get(ATTR_FORECAST_CONDITION) == 'lightning-rainy'
        assert forecast[0].get(ATTR_FORECAST_PRECIP_PROB) == 40
        assert forecast[0].get(ATTR_FORECAST_TEMP) == 41
        assert forecast[0].get(ATTR_FORECAST_TIME) == \
            '2018-12-21T15:00:00-05:00'
        assert forecast[0].get(ATTR_FORECAST_WIND_BEARING) == 180
        assert forecast[0].get(ATTR_FORECAST_WIND_SPEED) == 9

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_w_station(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with station."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'platform': 'nws',
                'station': 'STNB',
                'api_key': 'test_email',
            }
        })

        assert self.hass.states.get('weather.stnb')

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_w_no_name(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform w no name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

        assert self.hass.states.get('weather.' + STN)

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test__hourly(self, mock_metar, mock_pynws):
        """Test for successfully setting up hourly forecast."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HourlyWeather',
                'platform': 'nws',
                'api_key': 'test_email',
                'mode': 'hourly',
            }
        })

        state = self.hass.states.get('weather.hourlyweather')
        data = state.attributes

        forecast = data.get(ATTR_FORECAST)
        assert forecast[0].get(ATTR_FORECAST_CONDITION) == 'clear-night'
        assert forecast[0].get(ATTR_FORECAST_PRECIP_PROB) is None
        assert forecast[0].get(ATTR_FORECAST_TEMP) == 32
        assert forecast[0].get(ATTR_FORECAST_TIME) == \
            '2018-12-22T04:00:00-05:00'
        assert forecast[0].get(ATTR_FORECAST_WIND_BEARING) == 0
        assert forecast[0].get(ATTR_FORECAST_WIND_SPEED) == 4

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_daynight(self, mock_metar, mock_pynws):
        """Test for successfully setting up daynight forecast."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'platform': 'nws',
                'api_key': 'test_email',
                'mode': 'daynight',
            }
        })
        assert self.hass.states.get('weather.' + STN)

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_latlon(self, mock_metar, mock_pynws):
        """Test for successsfully setting up the NWS platform with lat/lon."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'platform': 'nws',
                'api_key': 'test_email',
                'latitude': self.lat,
                'longitude': self.lon,
            }
        })
        assert self.hass.states.get('weather.' + STN)

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_setup_failure_mode(self, mock_metar, mock_pynws):
        """Test for unsuccessfully setting up incorrect mode."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'platform': 'nws',
                'api_key': 'test_email',
                'mode': 'abc',
            }
        })
        assert self.hass.states.get('weather.' + STN) is None

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_setup_failure_no_apikey(self, mock_metar, mock_pynws):
        """Test for unsuccessfully setting up without api_key."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'platform': 'nws',
                }
        })

        assert self.hass.states.get('weather.' + STN) is None


class TestNwsMetric(unittest.TestCase):
    """Test the NWS weather component using metric units."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        self.lat = self.hass.config.latitude = 40.00
        self.lon = self.hass.config.longitude = -8.00

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_metric(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

        state = self.hass.states.get('weather.homeweather')
        assert state.state == 'sunny'

        data = state.attributes
        assert data.get(ATTR_WEATHER_TEMPERATURE) == \
            display_temp(self.hass, 7, TEMP_CELSIUS, PRECISION_WHOLE)

        assert data.get(ATTR_WEATHER_HUMIDITY) == 10
        assert data.get(ATTR_WEATHER_PRESSURE) == round(
            convert_pressure(30000, PRESSURE_PA, PRESSURE_HPA))
        # m/s to km/hr
        assert data.get(ATTR_WEATHER_WIND_SPEED) == round(10 * 3.6)
        assert data.get(ATTR_WEATHER_WIND_BEARING) == 180
        assert data.get(ATTR_WEATHER_VISIBILITY) == round(
            convert_distance(10000, LENGTH_METERS, LENGTH_KILOMETERS))
        assert state.attributes.get('friendly_name') == 'HomeWeather'

        forecast = data.get(ATTR_FORECAST)
        assert forecast[0].get(ATTR_FORECAST_CONDITION) == 'lightning-rainy'
        assert forecast[0].get(ATTR_FORECAST_PRECIP_PROB) == 40
        assert forecast[0].get(ATTR_FORECAST_TEMP) == round(
            convert_temperature(41, TEMP_FAHRENHEIT, TEMP_CELSIUS))
        assert forecast[0].get(ATTR_FORECAST_TIME) == \
            '2018-12-21T15:00:00-05:00'
        assert forecast[0].get(ATTR_FORECAST_WIND_BEARING) == 180
        assert forecast[0].get(ATTR_FORECAST_WIND_SPEED) == round(
            convert_distance(9, LENGTH_MILES, LENGTH_KILOMETERS))


class MockNws_Metar(MockNws):
    """Mock Station from pynws."""

    def __init__(self, websession, latlon, userid):
        """Init mock nws."""
        pass

    async def observations(self, limit):
        """Mock Observation."""
        return OBS_METAR


class TestNWS_Metar(unittest.TestCase):
    """Test the NWS weather component with metar code."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = IMPERIAL_SYSTEM
        self.lat = self.hass.config.latitude = 40.00
        self.lon = self.hass.config.longitude = -8.00

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws_Metar)
    @patch("metar.Metar.Metar", new=MockMetar)
    def test_metar(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

        from metar import Metar
        truth = Metar.Metar(METAR_MSG)
        state = self.hass.states.get('weather.homeweather')
        data = state.attributes

        temp_f = convert_temperature(truth.temp.value(), TEMP_CELSIUS,
                                     TEMP_FAHRENHEIT)
        assert data.get(ATTR_WEATHER_TEMPERATURE) == \
            display_temp(self.hass, temp_f, TEMP_FAHRENHEIT, PRECISION_WHOLE)
        assert data.get(ATTR_WEATHER_HUMIDITY) is None
        assert data.get(ATTR_WEATHER_PRESSURE) == round(
            convert_pressure(truth.press.value(), PRESSURE_HPA, PRESSURE_INHG),
            2)

        wind_speed_mi_s = convert_distance(
            truth.wind_speed.value(), LENGTH_METERS, LENGTH_MILES)
        assert data.get(ATTR_WEATHER_WIND_SPEED) == round(
            wind_speed_mi_s * 3600)
        assert data.get(ATTR_WEATHER_WIND_BEARING) == truth.wind_dir.value()
        vis = convert_distance(truth.vis.value(), LENGTH_METERS, LENGTH_MILES)
        assert data.get(ATTR_WEATHER_VISIBILITY) == round(vis)


class MockNwsFailObs(MockNws):
    """Mock Station from pynws."""

    def __init__(self, websession, latlon, userid):
        """Init mock nws."""
        pass

    async def observations(self, limit):
        """Mock Observation."""
        raise aiohttp.ClientError


class MockNwsFailStn(MockNws):
    """Mock Station from pynws."""

    def __init__(self, websession, latlon, userid):
        """Init mock nws."""
        pass

    async def stations(self):
        """Mock Observation."""
        raise aiohttp.ClientError


class MockNwsFailFore(MockNws):
    """Mock Station from pynws."""

    def __init__(self, websession, latlon, userid):
        """Init mock nws."""
        pass

    async def forecast(self):
        """Mock Observation."""
        raise aiohttp.ClientError


class MockNws_NoObs(MockNws):
    """Mock Station from pynws."""

    def __init__(self, websession, latlon, userid):
        """Init mock nws."""
        pass

    async def observations(self, limit):
        """Mock Observation."""
        return OBS_NONE


class TestFailures(unittest.TestCase):
    """Test the NWS weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = IMPERIAL_SYSTEM
        self.lat = self.hass.config.latitude = 40.00
        self.lon = self.hass.config.longitude = -8.00

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNwsFailObs)
    def test_obs_fail(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNwsFailStn)
    def test_fail_stn(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })
        state = self.hass.states.get('weather.homeweather')
        assert state is None

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNwsFailFore)
    def test_fail_fore(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws_NoObs)
    def test_no_obs(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })
        state = self.hass.states.get('weather.homeweather')
        assert state.state == 'unknown'

    @MockDependency("metar")
    @MockDependency("pynws")
    @patch("pynws.Nws", new=MockNws)
    def test_no_lat(self, mock_metar, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        hass = self.hass
        hass.config.latitude = None

        assert setup_component(self.hass, weather.DOMAIN, {
            'weather': {
                'name': 'HomeWeather',
                'platform': 'nws',
                'api_key': 'test_email',
            }
        })

        state = self.hass.states.get('weather.homeweather')
        assert state is None
