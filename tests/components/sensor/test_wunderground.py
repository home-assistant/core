"""The tests for the WUnderground platform."""
import unittest

from homeassistant.components.sensor import wunderground
from homeassistant.const import TEMP_CELSIUS, LENGTH_INCHES

from tests.common import get_test_home_assistant

VALID_CONFIG_PWS = {
    'platform': 'wunderground',
    'api_key': 'foo',
    'pws_id': 'bar',
    'monitored_conditions': [
        'weather', 'feelslike_c', 'alerts', 'elevation', 'location'
    ]
}

VALID_CONFIG = {
    'platform': 'wunderground',
    'api_key': 'foo',
    'monitored_conditions': [
        'weather', 'feelslike_c', 'alerts', 'elevation', 'location',
        'weather_1d_metric', 'precip_1d_in'
    ]
}

INVALID_CONFIG = {
    'platform': 'wunderground',
    'api_key': 'BOB',
    'pws_id': 'bar',
    'lang': 'foo',
    'monitored_conditions': [
        'weather', 'feelslike_c', 'alerts'
    ]
}

FEELS_LIKE = '40'
WEATHER = 'Clear'
HTTPS_ICON_URL = 'https://icons.wxug.com/i/c/k/clear.gif'
ALERT_MESSAGE = 'This is a test alert message'
FORECAST_TEXT = 'Mostly Cloudy. Fog overnight.'
PRECIP_IN = 0.03


def mocked_requests_get(*args, **kwargs):
    """Mock requests.get invocations."""
    class MockResponse:
        """Class to represent a mocked response."""

        def __init__(self, json_data, status_code):
            """Initialize the mock response class."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Return the json of the response."""
            return self.json_data

    if str(args[0]).startswith('http://api.wunderground.com/api/foo/'):
        return MockResponse({
            "response": {
                "version": "0.1",
                "termsofService":
                    "http://www.wunderground.com/weather/api/d/terms.html",
                "features": {
                    "conditions": 1,
                    "alerts": 1,
                    "forecast": 1,
                }
            }, "current_observation": {
                "image": {
                    "url":
                        'http://icons.wxug.com/graphics/wu2/logo_130x80.png',
                    "title": "Weather Underground",
                    "link": "http://www.wunderground.com"
                },
                "feelslike_c": FEELS_LIKE,
                "weather": WEATHER,
                "icon_url": 'http://icons.wxug.com/i/c/k/clear.gif',
                "display_location": {
                    "city": "Holly Springs",
                    "country": "US",
                    "full": "Holly Springs, NC"
                },
                "observation_location": {
                    "elevation": "413 ft",
                    "full": "Twin Lake, Holly Springs, North Carolina"
                },
            }, "alerts": [
                {
                    "type": 'FLO',
                    "description": "Areal Flood Warning",
                    "date": "9:36 PM CDT on September 22, 2016",
                    "expires": "10:00 AM CDT on September 23, 2016",
                    "message": ALERT_MESSAGE,
                },

            ], "forecast": {
                "txt_forecast": {
                    "date": "22:35 CEST",
                    "forecastday": [
                        {
                            "period": 0,
                            "icon_url":
                                "http://icons.wxug.com/i/c/k/clear.gif",
                            "title": "Tuesday",
                            "fcttext": FORECAST_TEXT,
                            "fcttext_metric": FORECAST_TEXT,
                            "pop": "0"
                        },
                    ],
                }, "simpleforecast": {
                    "forecastday": [
                        {
                            "date": {
                                "pretty": "19:00 CEST 4. Duben 2017",
                            },
                            "period": 1,
                            "high": {
                                "fahrenheit": "56",
                                "celsius": "13",
                            },
                            "low": {
                                "fahrenheit": "43",
                                "celsius": "6",
                            },
                            "conditions": "Možnost deště",
                            "icon_url":
                                "http://icons.wxug.com/i/c/k/chancerain.gif",
                            "qpf_allday": {
                                "in": PRECIP_IN,
                                "mm": 1,
                            },
                            "maxwind": {
                                "mph": 0,
                                "kph": 0,
                                "dir": "",
                                "degrees": 0,
                            },
                            "avewind": {
                                "mph": 0,
                                "kph": 0,
                                "dir": "severní",
                                "degrees": 0
                            }
                        },
                    ],
                },
            },
        }, 200)
    else:
        return MockResponse({
            "response": {
                "version": "0.1",
                "termsofService":
                    "http://www.wunderground.com/weather/api/d/terms.html",
                "features": {},
                "error": {
                    "type": "keynotfound",
                    "description": "this key does not exist"
                }
            }
        }, 200)


class TestWundergroundSetup(unittest.TestCase):
    """Test the WUnderground platform."""

    # pylint: disable=invalid-name
    DEVICES = []

    def add_devices(self, devices):
        """Mock add devices."""
        for device in devices:
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this testcase class."""
        self.DEVICES = []
        self.hass = get_test_home_assistant()
        self.key = 'foo'
        self.config = VALID_CONFIG_PWS
        self.lat = 37.8267
        self.lon = -122.423
        self.hass.config.latitude = self.lat
        self.hass.config.longitude = self.lon

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_setup(self, req_mock):
        """Test that the component is loaded if passed in PWS Id."""
        self.assertTrue(
            wunderground.setup_platform(self.hass, VALID_CONFIG_PWS,
                                        self.add_devices, None))
        self.assertTrue(
            wunderground.setup_platform(self.hass, VALID_CONFIG,
                                        self.add_devices, None))

        self.assertTrue(
            wunderground.setup_platform(self.hass, INVALID_CONFIG,
                                        self.add_devices, None))

    @unittest.mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_sensor(self, req_mock):
        """Test the WUnderground sensor class and methods."""
        wunderground.setup_platform(self.hass, VALID_CONFIG, self.add_devices,
                                    None)
        for device in self.DEVICES:
            device.update()
            self.assertTrue(str(device.name).startswith('PWS_'))
            if device.name == 'PWS_weather':
                self.assertEqual(HTTPS_ICON_URL, device.entity_picture)
                self.assertEqual(WEATHER, device.state)
                self.assertIsNone(device.unit_of_measurement)
            elif device.name == 'PWS_alerts':
                self.assertEqual(1, device.state)
                self.assertEqual(ALERT_MESSAGE,
                                 device.device_state_attributes['Message'])
                self.assertIsNone(device.entity_picture)
            elif device.name == 'PWS_location':
                self.assertEqual('Holly Springs, NC', device.state)
            elif device.name == 'PWS_elevation':
                self.assertEqual('413', device.state)
            elif device.name == 'PWS_feelslike_c':
                self.assertIsNone(device.entity_picture)
                self.assertEqual(FEELS_LIKE, device.state)
                self.assertEqual(TEMP_CELSIUS, device.unit_of_measurement)
            elif device.name == 'PWS_weather_1d_metric':
                self.assertEqual(FORECAST_TEXT, device.state)
            else:
                self.assertEqual(device.name, 'PWS_precip_1d_in')
                self.assertEqual(PRECIP_IN, device.state)
                self.assertEqual(LENGTH_INCHES, device.unit_of_measurement)
