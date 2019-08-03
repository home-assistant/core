"""Tests for the NWS weather component."""
import unittest
from unittest.mock import patch

import aiohttp

from homeassistant.components import weather
from homeassistant.components.nws.weather import ATTR_FORECAST_PRECIP_PROB
from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
)

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRECISION_WHOLE,
    PRESSURE_INHG,
    PRESSURE_PA,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.temperature import display_temp
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, MockDependency

OBS = {
    "temperature": 7,
    "relativeHumidity": 10,
    "windDirection": 180,
    "visibility": 10000,
    "windSpeed": 10,
    "seaLevelPressure": 30000,
    "iconTime": "day",
    "iconWeather": (("Fair/clear", None),),
}

FORE = [
    {
        "temperature": 41,
        "windBearing": 180,
        "windSpeedAvg": 9,
        "iconTime": "day",
        "startTime": "2018-12-21T15:00:00-05:00",
        "iconWeather": (("Fair/Clear", None), ("Thunderstorm (high cloud cover)", 40)),
    }
]

STN = "STNA"


class MockNws:
    """Mock Station from pynws."""

    data_obs = None
    data_fore = None

    error_obs = False
    error_fore = False
    error_stn = False

    def __init__(self, lat, lon, userid, mode, session):
        """Init mock nws."""
        self.station = None
        self.stations = None

    async def update_observation(self):
        """Mock observation update."""
        if self.error_obs:
            raise aiohttp.ClientError
        return

    async def update_forecast(self):
        """Mock forecast update."""
        if self.error_fore:
            raise aiohttp.ClientError
        return

    @property
    def observation(self):
        """Mock Observation."""
        return self.data_obs

    @property
    def forecast(self):
        """Mock Forecast."""
        return self.data_fore

    async def set_station(self, station=None):
        """Mock stations."""
        if self.error_stn:
            raise aiohttp.ClientError
        self.stations = [STN]
        self.station = station or STN
        return


class TestNWS(unittest.TestCase):
    """Test the NWS weather component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = IMPERIAL_SYSTEM
        self.lat = self.hass.config.latitude = 40.00
        self.lon = self.hass.config.longitude = -8.00

        # Initialize class variables as tests modify them
        MockNws.data_obs = None
        MockNws.data_fore = None

        MockNws.error_obs = False
        MockNws.error_fore = False
        MockNws.error_stn = False

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws(self, mock_pynws):
        """Test for successfully setting up with imperial."""
        mock_pynws.SimpleNWS.data_obs = OBS
        mock_pynws.SimpleNWS.data_fore = FORE

        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        assert state.state == "sunny"

        data = state.attributes
        temp_f = convert_temperature(7, TEMP_CELSIUS, TEMP_FAHRENHEIT)
        assert data.get(ATTR_WEATHER_TEMPERATURE) == display_temp(
            self.hass, temp_f, TEMP_FAHRENHEIT, PRECISION_WHOLE
        )
        assert data.get(ATTR_WEATHER_HUMIDITY) == 10
        assert data.get(ATTR_WEATHER_PRESSURE) == round(
            convert_pressure(30000, PRESSURE_PA, PRESSURE_INHG), 2
        )
        assert data.get(ATTR_WEATHER_WIND_SPEED) == round(10 * 2.237)
        assert data.get(ATTR_WEATHER_WIND_BEARING) == 180
        assert data.get(ATTR_WEATHER_VISIBILITY) == round(
            convert_distance(10000, LENGTH_METERS, LENGTH_MILES)
        )
        assert state.attributes.get("friendly_name") == "HomeWeather"

        forecast = data.get(ATTR_FORECAST)
        assert forecast[0].get(ATTR_FORECAST_CONDITION) == "lightning-rainy"
        assert forecast[0].get(ATTR_FORECAST_PRECIP_PROB) == 40
        assert forecast[0].get(ATTR_FORECAST_TEMP) == 41
        assert forecast[0].get(ATTR_FORECAST_TIME) == "2018-12-21T15:00:00-05:00"
        assert forecast[0].get(ATTR_FORECAST_WIND_BEARING) == 180
        assert forecast[0].get(ATTR_FORECAST_WIND_SPEED) == 9

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws_metric(self, mock_pynws):
        """Test for successfully setting up with metric."""
        mock_pynws.SimpleNWS.data_obs = OBS
        mock_pynws.SimpleNWS.data_fore = FORE

        self.hass.config.units = METRIC_SYSTEM
        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        assert state.state == "sunny"

        data = state.attributes
        temp_f = convert_temperature(7, TEMP_CELSIUS, TEMP_FAHRENHEIT)
        assert data.get(ATTR_WEATHER_TEMPERATURE) == display_temp(
            self.hass, temp_f, TEMP_FAHRENHEIT, PRECISION_WHOLE
        )
        assert data.get(ATTR_WEATHER_HUMIDITY) == 10
        assert data.get(ATTR_WEATHER_PRESSURE) == round(
            convert_pressure(30000, PRESSURE_PA, PRESSURE_HPA)
        )
        assert data.get(ATTR_WEATHER_WIND_SPEED) == round(3.6 * 10)
        assert data.get(ATTR_WEATHER_WIND_BEARING) == 180
        assert data.get(ATTR_WEATHER_VISIBILITY) == round(
            convert_distance(10000, LENGTH_METERS, LENGTH_KILOMETERS)
        )
        assert state.attributes.get("friendly_name") == "HomeWeather"

        forecast = data.get(ATTR_FORECAST)
        assert forecast[0].get(ATTR_FORECAST_CONDITION) == "lightning-rainy"
        assert forecast[0].get(ATTR_FORECAST_PRECIP_PROB) == 40
        assert forecast[0].get(ATTR_FORECAST_TEMP) == convert_temperature(
            41, TEMP_FAHRENHEIT, TEMP_CELSIUS
        )
        assert forecast[0].get(ATTR_FORECAST_TIME) == "2018-12-21T15:00:00-05:00"
        assert forecast[0].get(ATTR_FORECAST_WIND_BEARING) == 180
        assert forecast[0].get(ATTR_FORECAST_WIND_SPEED) == round(
            convert_distance(9, LENGTH_MILES, LENGTH_KILOMETERS)
        )

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws_no_obs_fore1x(self, mock_pynws):
        """Test with no data."""
        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        assert state.state == "unknown"

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws_missing_valuess(self, mock_pynws):
        """Test with missing data."""
        mock_pynws.SimpleNWS.data_obs = {key: None for key in OBS}
        mock_pynws.SimpleNWS.data_fore = [{key: None for key in FORE[0]}]

        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        assert state.state == "unknown"

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws_error_obs(self, mock_pynws):
        """Test for successfully setting up the NWS platform with name."""
        mock_pynws.SimpleNWS.error_obs = True

        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        assert state.state == "unknown"

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws_error_fore(self, mock_pynws):
        """Test error forecast."""
        mock_pynws.SimpleNWS.error_fore = True
        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        data = state.attributes
        assert data.get("forecast") is None

    @MockDependency("pynws")
    @patch("pynws.SimpleNWS", new=MockNws)
    def test_nws_error_stn(self, mock_pynws):
        """Test station error.."""
        mock_pynws.SimpleNWS.error_stn = True
        assert setup_component(
            self.hass,
            weather.DOMAIN,
            {
                "weather": {
                    "name": "HomeWeather",
                    "platform": "nws",
                    "api_key": "test_email",
                }
            },
        )

        state = self.hass.states.get("weather.homeweather")
        assert state is None
