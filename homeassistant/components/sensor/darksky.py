"""
Support for Dark Sky weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.darksky/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from requests.exceptions import ConnectionError as ConnectError, \
    HTTPError, Timeout

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-forecastio==1.3.5']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Powered by Dark Sky"
CONF_UNITS = 'units'
CONF_UPDATE_INTERVAL = 'update_interval'
CONF_FORECAST = 'forecast'

DEFAULT_NAME = 'Dark Sky'

# Sensor types are defined like so:
# Name, si unit, us unit, ca unit, uk unit, uk2 unit
SENSOR_TYPES = {
    'summary': ['Summary', None, None, None, None, None, None, []],
    'minutely_summary': ['Minutely Summary',
                         None, None, None, None, None, None, []],
    'hourly_summary': ['Hourly Summary', None, None, None, None, None, None,
                       []],
    'daily_summary': ['Daily Summary', None, None, None, None, None, None, []],
    'icon': ['Icon', None, None, None, None, None, None,
             ['currently', 'hourly', 'daily']],
    'nearest_storm_distance': ['Nearest Storm Distance',
                               'km', 'm', 'km', 'km', 'm',
                               'mdi:weather-lightning', ['currently']],
    'nearest_storm_bearing': ['Nearest Storm Bearing',
                              '°', '°', '°', '°', '°',
                              'mdi:weather-lightning', ['currently']],
    'precip_type': ['Precip', None, None, None, None, None,
                    'mdi:weather-pouring',
                    ['currently', 'minutely', 'hourly', 'daily']],
    'precip_intensity': ['Precip Intensity',
                         'mm', 'in', 'mm', 'mm', 'mm', 'mdi:weather-rainy',
                         ['currently', 'minutely', 'hourly', 'daily']],
    'precip_probability': ['Precip Probability',
                           '%', '%', '%', '%', '%', 'mdi:water-percent',
                           ['currently', 'minutely', 'hourly', 'daily']],
    'temperature': ['Temperature',
                    '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer',
                    ['currently', 'hourly']],
    'apparent_temperature': ['Apparent Temperature',
                             '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer',
                             ['currently', 'hourly']],
    'dew_point': ['Dew point', '°C', '°F', '°C', '°C', '°C',
                  'mdi:thermometer', ['currently', 'hourly', 'daily']],
    'wind_speed': ['Wind Speed', 'm/s', 'mph', 'km/h', 'mph', 'mph',
                   'mdi:weather-windy', ['currently', 'hourly', 'daily']],
    'wind_bearing': ['Wind Bearing', '°', '°', '°', '°', '°', 'mdi:compass',
                     ['currently', 'hourly', 'daily']],
    'cloud_cover': ['Cloud Coverage', '%', '%', '%', '%', '%',
                    'mdi:weather-partlycloudy',
                    ['currently', 'hourly', 'daily']],
    'humidity': ['Humidity', '%', '%', '%', '%', '%', 'mdi:water-percent',
                 ['currently', 'hourly', 'daily']],
    'pressure': ['Pressure', 'mbar', 'mbar', 'mbar', 'mbar', 'mbar',
                 'mdi:gauge', ['currently', 'hourly', 'daily']],
    'visibility': ['Visibility', 'km', 'm', 'km', 'km', 'm', 'mdi:eye',
                   ['currently', 'hourly', 'daily']],
    'ozone': ['Ozone', 'DU', 'DU', 'DU', 'DU', 'DU', 'mdi:eye',
              ['currently', 'hourly', 'daily']],
    'apparent_temperature_max': ['Daily High Apparent Temperature',
                                 '°C', '°F', '°C', '°C', '°C',
                                 'mdi:thermometer',
                                 ['currently', 'hourly', 'daily']],
    'apparent_temperature_min': ['Daily Low Apparent Temperature',
                                 '°C', '°F', '°C', '°C', '°C',
                                 'mdi:thermometer',
                                 ['currently', 'hourly', 'daily']],
    'temperature_max': ['Daily High Temperature',
                        '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer',
                        ['currently', 'hourly', 'daily']],
    'temperature_min': ['Daily Low Temperature',
                        '°C', '°F', '°C', '°C', '°C', 'mdi:thermometer',
                        ['currently', 'hourly', 'daily']],
    'precip_intensity_max': ['Daily Max Precip Intensity',
                             'mm', 'in', 'mm', 'mm', 'mm', 'mdi:thermometer',
                             ['currently', 'hourly', 'daily']],
}

CONDITION_PICTURES = {
    'clear-day': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSAxMiw3QyAxNC43NjE0LDcgMTcsOS4yMzg1OCAxNywxMkMgMTcsMTQuNzYxNCAxNC43NjE0LDE3IDEyLDE3QyA5LjIzODU3LDE3IDcsMTQuNzYxNCA3LDEyQyA3LDkuMjM4NTggOS4yMzg1Nyw3IDEyLDcgWiBNIDEyLDkuMDAwMDFDIDEwLjM0MzEsOS4wMDAwMSA5LDEwLjM0MzIgOSwxMkMgOSwxMy42NTY5IDEwLjM0MzEsMTUgMTIsMTVDIDEzLjY1NjgsMTUgMTUsMTMuNjU2OSAxNSwxMkMgMTUsMTAuMzQzMiAxMy42NTY4LDkuMDAwMDEgMTIsOS4wMDAwMSBaIE0gMTIsMi4wMDAwMkwgMTQuMzk0MSw1LjQyMDExQyAxMy42NDcxLDUuMTQ4MjggMTIuODQwOSw1LjAwMDAxIDEyLDUuMDAwMDFDIDExLjE1OTEsNS4wMDAwMSAxMC4zNTI4LDUuMTQ4MjggOS42MDU5Myw1LjQyMDExTCAxMiwyLjAwMDAyIFogTSAzLjM0NDk1LDcuMDA5MDJMIDcuNTAzODgsNi42NDU3NUMgNi44OTUwMSw3LjE1NjY4IDYuMzYzNDgsNy43ODA3OSA1Ljk0MzAzLDguNTA5MDJDIDUuNTIyNTgsOS4yMzcyNiA1LjI0Nzg2LDEwLjAwOTYgNS4xMDk4MSwxMC43OTI0TCAzLjM0NDk1LDcuMDA5MDIgWiBNIDMuMzU1MzcsMTcuMDA5TCA1LjEyMDIyLDEzLjIyNTdDIDUuMjU4MjcsMTQuMDA4NCA1LjUzMywxNC43ODA4IDUuOTUzNDQsMTUuNTA5QyA2LjM3Mzg5LDE2LjIzNzMgNi45MDU0MywxNi44NjE0IDcuNTE0MjksMTcuMzcyM0wgMy4zNTUzNywxNy4wMDkgWiBNIDIwLjY0Niw3LjAwMzgyTCAxOC44ODEyLDEwLjc4NzJDIDE4Ljc0MzEsMTAuMDA0NCAxOC40Njg0LDkuMjMyMDUgMTguMDQ3OSw4LjUwMzgyQyAxNy42Mjc1LDcuNzc1NTkgMTcuMDk2LDcuMTUxNDggMTYuNDg3MSw2LjY0MDU0TCAyMC42NDYsNy4wMDM4MiBaIE0gMjAuNjM1NiwxNi45OTM0TCAxNi40NzY3LDE3LjM1NjdDIDE3LjA4NTUsMTYuODQ1NyAxNy42MTcxLDE2LjIyMTYgMTguMDM3NSwxNS40OTM0QyAxOC40NTgsMTQuNzY1MiAxOC43MzI3LDEzLjk5MjggMTguODcwNywxMy4yMUwgMjAuNjM1NiwxNi45OTM0IFogTSAxMS45NzkyLDIxLjk3OTJMIDkuNTg1MDksMTguNTU5MUMgMTAuMzMyLDE4LjgzMDkgMTEuMTM4MywxOC45NzkyIDExLjk3OTIsMTguOTc5MkMgMTIuODIwMSwxOC45NzkyIDEzLjYyNjMsMTguODMwOSAxNC4zNzMyLDE4LjU1OTFMIDExLjk3OTIsMjEuOTc5MiBaICIvPgo8L3N2Zz4K',
    'clear-night': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSAxNy43NTMzLDQuMDkwMTdMIDE1LjIyMDUsNi4wMzExNUwgMTYuMTI4Nyw5LjA5MDE3TCAxMy41LDcuMjgxMTVMIDEwLjg3MTMsOS4wOTAxN0wgMTEuNzc5NSw2LjAzMTE1TCA5LjI0Njc1LDQuMDkwMTdMIDEyLjQzNjcsNC4wMDg2MUwgMTMuNSwxTCAxNC41NjMzLDQuMDA4NjFMIDE3Ljc1MzMsNC4wOTAxNyBaIE0gMjEuMjUsMTAuOTk4TCAxOS42MTI0LDEyLjI1M0wgMjAuMTk5NiwxNC4yMzA4TCAxOC41LDEzLjA2MTJMIDE2LjgwMDQsMTQuMjMwOEwgMTcuMzg3NiwxMi4yNTNMIDE1Ljc1LDEwLjk5OEwgMTcuODEyNSwxMC45NDUzTCAxOC41LDlMIDE5LjE4NzUsMTAuOTQ1M0wgMjEuMjUsMTAuOTk4IFogTSAxOC45NzA4LDE1Ljk0NTFDIDE5LjgwMDksMTUuODY2MSAyMC42OTM1LDE3LjA0NzkgMjAuMTU3NiwxNy43OTkxQyAxOS44MzkzLDE4LjI0NTMgMTkuNDgsMTguNjcxMyAxOS4wNzk1LDE5LjA3MTdDIDE1LjE3NDMsMjIuOTc2OSA4Ljg0MjY2LDIyLjk3NjkgNC45Mzc0MSwxOS4wNzE3QyAxLjAzMjE3LDE1LjE2NjQgMS4wMzIxNyw4LjgzNDc3IDQuOTM3NDEsNC45Mjk1M0MgNS4zMzc4Miw0LjUyOTEyIDUuNzYzNzMsNC4xNjk3NyA2LjIwOTkzLDMuODUxNDdDIDYuOTYxMTgsMy4zMTU1NSA4LjE0MjkzLDQuMjA4MTkgOC4wNjQwMiw1LjAzODNDIDcuNzkxNTUsNy45MDQ3IDguNzUyODIsMTAuODY2MiAxMC45NDc4LDEzLjA2MTNDIDEzLjE0MjgsMTUuMjU2MyAxNi4xMDQ0LDE2LjIxNzUgMTguOTcwOCwxNS45NDUxIFogTSAxNy4zMzQsMTcuOTcwN0MgMTQuNDk1LDE3LjgwOTQgMTEuNzAyNSwxNi42NDQzIDkuNTMzNjEsMTQuNDc1NUMgNy4zNjQ3MywxMi4zMDY2IDYuMTk5NjMsOS41MTQwMyA2LjAzODMzLDYuNjc1MUMgMy4yMzExOCw5LjgxNjM5IDMuMzM1NjEsMTQuNjQxNCA2LjM1MTYzLDE3LjY1NzRDIDkuMzY3NjQsMjAuNjczNSAxNC4xOTI3LDIwLjc3NzkgMTcuMzM0LDE3Ljk3MDcgWiAiLz4KPC9zdmc+Cg==',
    'rain': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE0QyA2LjU1MjI5LDE0IDcsMTQuNDQ3NyA3LDE1QyA3LDE1LjU1MjMgNi41NTIyOCwxNiA2LDE2QyAzLjIzODU4LDE2IDEsMTMuNzYxNCAxLDExQyAxLDguMjM5MTkgMy4yMzc1OCw2LjAwMDk5IDUuOTk4MTcsNkMgNi45Nzc3MywzLjY1MTA1IDkuMjk2MDUsMi4wMDAwMSAxMiwyLjAwMDAxQyAxNS40MzI4LDIuMDAwMDEgMTguMjQ0MSw0LjY2MTE1IDE4LjQ4MzUsOC4wMzMwNEwgMTksOEMgMjEuMjA5MSw4IDIzLDkuNzkwODYgMjMsMTJDIDIzLDE0LjIwOTEgMjEuMjA5MSwxNiAxOSwxNkwgMTgsMTZDIDE3LjQ0NzcsMTYgMTcsMTUuNTUyMyAxNywxNUMgMTcsMTQuNDQ3NyAxNy40NDc3LDE0IDE4LDE0TCAxOSwxNEMgMjAuMTA0NiwxNCAyMSwxMy4xMDQ2IDIxLDEyQyAyMSwxMC44OTU0IDIwLjEwNDYsMTAgMTksMTBMIDE3LDEwTCAxNyw5QyAxNyw2LjIzODU4IDE0Ljc2MTQsNCAxMiw0QyA5LjUxMjg0LDQgNy40NDk4Miw1LjgxNiA3LjA2NDU2LDguMTk0MzdDIDYuNzMzNzIsOC4wNjg3NyA2LjM3NDg5LDggNiw4QyA0LjM0MzE1LDggMyw5LjM0MzE1IDMsMTFDIDMsMTIuNjU2OSA0LjM0MzE1LDE0IDYsMTQgWiBNIDE0LjgyODUsMTUuNjcxNEMgMTYuMzkwNSwxNy4yMzM0IDE2LjM5MDUsMTkuNTE2NSAxNC44Mjg1LDIxLjA3ODVDIDE0LjA0OCwyMS44NTk1IDEzLjAyMzksMjIgMTEuOTk5OSwyMkMgMTAuOTc1OSwyMiA5Ljk1MjM5LDIxLjg1OTUgOS4xNzE5LDIxLjA3ODVDIDcuNjA5MzcsMTkuNTE2NSA3LjYwOTM3LDE3LjIzMzkgOS4xNzE5LDE1LjY3MTRMIDEyLjAwMDUsMTAuOTk5NUwgMTQuODI4NSwxNS42NzE0IFogTSAxMy40MTQyLDE2LjY5MkwgMTIuMDAwMiwxNC4yNDk5TCAxMC41ODU5LDE2LjY5MkMgOS44MDQ2MiwxNy41MDg3IDkuODA0NjIsMTguNzAxOCAxMC41ODU5LDE5LjUxODJDIDEwLjk3NjEsMTkuOTI2NSAxMS40ODc5LDE5Ljk5OTkgMTEuOTk5OSwxOS45OTk5QyAxMi41MTE5LDE5Ljk5OTkgMTMuMDIzOSwxOS45MjY1IDEzLjQxNDIsMTkuNTE4MkMgMTQuMTk1MiwxOC43MDE4IDE0LjE5NTIsMTcuNTA4NCAxMy40MTQyLDE2LjY5MiBaICIvPgo8L3N2Zz4K',
    'snow': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE0QyA2LjU1MjI5LDE0IDcsMTQuNDQ3NyA3LDE1QyA3LDE1LjU1MjMgNi41NTIyOCwxNiA2LDE2QyAzLjIzODU4LDE2IDEsMTMuNzYxNCAxLDExQyAxLDguMjM5MTkgMy4yMzc1OCw2LjAwMDk5IDUuOTk4MTcsNkMgNi45Nzc3MywzLjY1MTA1IDkuMjk2MDUsMi4wMDAwMSAxMiwyLjAwMDAxQyAxNS40MzI4LDIuMDAwMDEgMTguMjQ0MSw0LjY2MTE1IDE4LjQ4MzUsOC4wMzMwNEwgMTksOEMgMjEuMjA5MSw4IDIzLDkuNzkwODYgMjMsMTJDIDIzLDE0LjIwOTEgMjEuMjA5MSwxNiAxOSwxNkwgMTgsMTZDIDE3LjQ0NzcsMTYgMTcsMTUuNTUyMyAxNywxNUMgMTcsMTQuNDQ3NyAxNy40NDc3LDE0IDE4LDE0TCAxOSwxNEMgMjAuMTA0NiwxNCAyMSwxMy4xMDQ2IDIxLDEyQyAyMSwxMC44OTU0IDIwLjEwNDYsMTAgMTksMTBMIDE3LDEwTCAxNyw5QyAxNyw2LjIzODU4IDE0Ljc2MTQsNCAxMiw0QyA5LjUxMjg0LDQgNy40NDk4Miw1LjgxNiA3LjA2NDU2LDguMTk0MzdDIDYuNzMzNzIsOC4wNjg3NyA2LjM3NDg5LDggNiw4QyA0LjM0MzE1LDggMyw5LjM0MzE1IDMsMTFDIDMsMTIuNjU2OSA0LjM0MzE1LDE0IDYsMTQgWiBNIDcuODc3NDgsMTguMDY5NEwgMTAuMDY4MiwxNy40ODI0TCA4LjQ2NDQ3LDE1Ljg3ODdDIDguMDczOTUsMTUuNDg4MiA4LjA3Mzk1LDE0Ljg1NSA4LjQ2NDQ3LDE0LjQ2NDVDIDguODU0OTksMTQuMDczOSA5LjQ4ODE2LDE0LjA3MzkgOS44Nzg2OCwxNC40NjQ1TCAxMS40ODI0LDE2LjA2ODFMIDEyLjA2OTMsMTMuODc3NUMgMTIuMjEyMywxMy4zNDQgMTIuNzYwNiwxMy4wMjc0IDEzLjI5NDEsMTMuMTcwNEMgMTMuODI3NiwxMy4zMTMzIDE0LjE0NDEsMTMuODYxNyAxNC4wMDEyLDE0LjM5NTFMIDEzLjQxNDIsMTYuNTg1OEwgMTUuNjA0OSwxNS45OTg4QyAxNi4xMzgzLDE1Ljg1NTkgMTYuNjg2NywxNi4xNzI0IDE2LjgyOTYsMTYuNzA1OUMgMTYuOTcyNiwxNy4yMzk0IDE2LjY1NiwxNy43ODc3IDE2LjEyMjUsMTcuOTMwN0wgMTMuOTMxOSwxOC41MTc2TCAxNS41MzU1LDIwLjEyMTNDIDE1LjkyNjEsMjAuNTExOCAxNS45MjYxLDIxLjE0NSAxNS41MzU1LDIxLjUzNTVDIDE1LjE0NSwyMS45MjYxIDE0LjUxMTgsMjEuOTI2MSAxNC4xMjEzLDIxLjUzNTVMIDEyLjUxNzYsMTkuOTMxOEwgMTEuOTMwNiwyMi4xMjI1QyAxMS43ODc3LDIyLjY1NiAxMS4yMzk0LDIyLjk3MjYgMTAuNzA1OSwyMi44Mjk2QyAxMC4xNzI0LDIyLjY4NjcgOS44NTU4NSwyMi4xMzgzIDkuOTk4NzksMjEuNjA0OUwgMTAuNTg1OCwxOS40MTQyTCA4LjM5NTExLDIwLjAwMTJDIDcuODYxNjUsMjAuMTQ0MSA3LjMxMzMxLDE5LjgyNzYgNy4xNzAzNywxOS4yOTQxQyA3LjAyNzQzLDE4Ljc2MDYgNy4zNDQwMSwxOC4yMTIzIDcuODc3NDgsMTguMDY5NCBaICIvPgo8L3N2Zz4K',
    'sleet': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE0QyA2LjU1MjI5LDE0IDcsMTQuNDQ3NyA3LDE1QyA3LDE1LjU1MjMgNi41NTIyOCwxNiA2LDE2QyAzLjIzODU4LDE2IDEsMTMuNzYxNCAxLDExQyAxLDguMjM5MTkgMy4yMzc1OCw2LjAwMDk5IDUuOTk4MTcsNkMgNi45Nzc3MywzLjY1MTA1IDkuMjk2MDUsMi4wMDAwMSAxMiwyLjAwMDAxQyAxNS40MzI4LDIuMDAwMDEgMTguMjQ0MSw0LjY2MTE1IDE4LjQ4MzUsOC4wMzMwNEwgMTksOEMgMjEuMjA5MSw4IDIzLDkuNzkwODYgMjMsMTJDIDIzLDE0LjIwOTEgMjEuMjA5MSwxNiAxOSwxNkwgMTgsMTZDIDE3LjQ0NzcsMTYgMTcsMTUuNTUyMyAxNywxNUMgMTcsMTQuNDQ3NyAxNy40NDc3LDE0IDE4LDE0TCAxOSwxNEMgMjAuMTA0NiwxNCAyMSwxMy4xMDQ2IDIxLDEyQyAyMSwxMC44OTU0IDIwLjEwNDYsMTAgMTksMTBMIDE3LDEwTCAxNyw5QyAxNyw2LjIzODU4IDE0Ljc2MTQsNCAxMiw0QyA5LjUxMjg0LDQgNy40NDk4Miw1LjgxNiA3LjA2NDU2LDguMTk0MzdDIDYuNzMzNzIsOC4wNjg3NyA2LjM3NDg5LDggNiw4QyA0LjM0MzE1LDggMyw5LjM0MzE1IDMsMTFDIDMsMTIuNjU2OSA0LjM0MzE1LDE0IDYsMTQgWiBNIDEwLDE4QyAxMS4xMDQ2LDE4IDEyLDE4Ljg5NTQgMTIsMjBDIDEyLDIxLjEwNDYgMTEuMTA0NiwyMiAxMCwyMkMgOC44OTU0MywyMiA4LDIxLjEwNDYgOCwyMEMgOCwxOC44OTU0IDguODk1NDMsMTggMTAsMTggWiBNIDE0LjUsMTZDIDE1LjMyODQsMTYgMTYsMTYuNjcxNiAxNiwxNy41QyAxNiwxOC4zMjg0IDE1LjMyODQsMTkgMTQuNSwxOUMgMTMuNjcxNiwxOSAxMywxOC4zMjg0IDEzLDE3LjVDIDEzLDE2LjY3MTYgMTMuNjcxNiwxNiAxNC41LDE2IFogTSAxMC41LDEyQyAxMS4zMjg0LDEyIDEyLDEyLjY3MTYgMTIsMTMuNUMgMTIsMTQuMzI4NCAxMS4zMjg0LDE1IDEwLjUsMTVDIDkuNjcxNTcsMTUgOSwxNC4zMjg0IDksMTMuNUMgOSwxMi42NzE2IDkuNjcxNTcsMTIgMTAuNSwxMiBaICIvPgo8L3N2Zz4K',
    'wind': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA0LDEwQyAzLjQ0NzcxLDEwIDMsOS41NTIyOSAzLDlDIDMsOC40NDc3MiAzLjQ0NzcyLDggNCw4TCAxMiw4QyAxMy4xMDQ2LDggMTQsNy4xMDQ1NyAxNCw2QyAxNCw0Ljg5NTQzIDEzLjEwNDYsNCAxMiw0QyAxMS40NDc3LDQgMTAuOTQ3Nyw0LjIyMzg2IDEwLjU4NTgsNC41ODU3OEMgMTAuMTk1Myw0Ljk3NjMxIDkuNTYyMDksNC45NzYzMSA5LjE3MTU3LDQuNTg1NzhDIDguNzgxMDQsNC4xOTUyNiA4Ljc4MTA0LDMuNTYyMDkgOS4xNzE1NywzLjE3MTU3QyA5Ljg5NTQzLDIuNDQ3NzIgMTAuODk1NCwyLjAwMDAxIDEyLDIuMDAwMDFDIDE0LjIwOTEsMi4wMDAwMSAxNiwzLjc5MDg2IDE2LDZDIDE2LDguMjA5MTQgMTQuMjA5MSwxMCAxMiwxMEwgNCwxMCBaIE0gMTksMTJDIDE5LjU1MjMsMTIgMjAsMTEuNTUyMyAyMCwxMUMgMjAsMTAuNDQ3NyAxOS41NTIzLDEwIDE5LDEwQyAxOC43MjM4LDEwIDE4LjQ3MzgsMTAuMTExOSAxOC4yOTI5LDEwLjI5MjlDIDE3LjkwMjQsMTAuNjgzNCAxNy4yNjkyLDEwLjY4MzQgMTYuODc4NywxMC4yOTI5QyAxNi40ODgxLDkuOTAyMzcgMTYuNDg4Miw5LjI2OTIgMTYuODc4Nyw4Ljg3ODY4QyAxNy40MjE2LDguMzM1NzkgMTguMTcxNiw4IDE5LDhDIDIwLjY1NjgsOCAyMiw5LjM0MzE1IDIyLDExQyAyMiwxMi42NTY5IDIwLjY1NjgsMTQgMTksMTRMIDUsMTRDIDQuNDQ3NzEsMTQgNCwxMy41NTIzIDQsMTNDIDQsMTIuNDQ3NyA0LjQ0NzcyLDEyIDUsMTJMIDE5LDEyIFogTSAxOCwxOEwgNCwxOEMgMy40NDc3MiwxOCAzLDE3LjU1MjMgMywxN0MgMywxNi40NDc3IDMuNDQ3NzEsMTYgNCwxNkwgMTgsMTZDIDE5LjY1NjgsMTYgMjEsMTcuMzQzMSAyMSwxOUMgMjEsMjAuNjU2OSAxOS42NTY4LDIyIDE4LDIyQyAxNy4xNzE2LDIyIDE2LjQyMTYsMjEuNjY0MiAxNS44Nzg3LDIxLjEyMTNDIDE1LjQ4ODIsMjAuNzMwOCAxNS40ODgxLDIwLjA5NzYgMTUuODc4NywxOS43MDcxQyAxNi4yNjkyLDE5LjMxNjYgMTYuOTAyNCwxOS4zMTY2IDE3LjI5MjksMTkuNzA3MUMgMTcuNDczOCwxOS44ODgxIDE3LjcyMzgsMjAgMTgsMjBDIDE4LjU1MjMsMjAgMTksMTkuNTUyMyAxOSwxOUMgMTksMTguNDQ3NyAxOC41NTIzLDE4IDE4LDE4IFogIi8+Cjwvc3ZnPgo=',
    'fog': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGQ9Ik0gMywxNUwgMTMsMTVDIDEzLjU1MjMsMTUgMTQsMTUuNDQ3NyAxNCwxNkMgMTQsMTYuNTUyMyAxMy41NTIzLDE3IDEzLDE3TCAzLDE3QyAyLjQ0NzcyLDE3IDIsMTYuNTUyMyAyLDE2QyAyLDE1LjQ0NzcgMi40NDc3MiwxNSAzLDE1IFogTSAxNiwxNUwgMjEsMTVDIDIxLjU1MjMsMTUgMjIsMTUuNDQ3NyAyMiwxNkMgMjIsMTYuNTUyMyAyMS41NTIzLDE3IDIxLDE3TCAxNiwxN0MgMTUuNDQ3NywxNyAxNSwxNi41NTIzIDE1LDE2QyAxNSwxNS40NDc3IDE1LjQ0NzcsMTUgMTYsMTUgWiBNIDEsMTJDIDEsOS4yMzkxOSAzLjIzNzU5LDcuMDAxIDUuOTk4MTcsN0MgNi45Nzc3Myw0LjY1MTA1IDkuMjk2MDUsMy4wMDAwMSAxMiwzLjAwMDAxQyAxNS40MzI4LDMuMDAwMDEgMTguMjQ0MSw1LjY2MTE1IDE4LjQ4MzUsOS4wMzMwNUwgMTksOUMgMjEuMTkyOCw5IDIyLjk3MzUsMTAuNzY0NSAyMi45OTk0LDEzTCAyMSwxM0MgMjEsMTEuODk1NCAyMC4xMDQ2LDExIDE5LDExTCAxNywxMUwgMTcsMTBDIDE3LDcuMjM4NTggMTQuNzYxNCw1LjAwMDAxIDEyLDUuMDAwMDFDIDkuNTEyODQsNS4wMDAwMSA3LjQ0OTgyLDYuODE2IDcuMDY0NTYsOS4xOTQzOEMgNi43MzM3Miw5LjA2ODc3IDYuMzc0ODksOS4wMDAwMSA2LDkuMDAwMDFDIDQuMzQzMTUsOS4wMDAwMSAzLDEwLjM0MzIgMywxMkMgMywxMi4zNTA2IDMuMDYwMTYsMTIuNjg3MiAzLjE3MDcxLDEzTCAxLjEwMDAyLDEzTCAxLDEyIFogTSAzLDE5TCA1LDE5QyA1LjU1MjI4LDE5IDYsMTkuNDQ3NyA2LDIwQyA2LDIwLjU1MjMgNS41NTIyOCwyMSA1LDIxTCAzLDIxQyAyLjQ0NzcyLDIxIDIsMjAuNTUyMyAyLDIwQyAyLDE5LjQ0NzcgMi40NDc3MiwxOSAzLDE5IFogTSA4LDE5TCAyMSwxOUMgMjEuNTUyMywxOSAyMiwxOS40NDc3IDIyLDIwQyAyMiwyMC41NTIzIDIxLjU1MjMsMjEgMjEsMjFMIDgsMjFDIDcuNDQ3NzEsMjEgNywyMC41NTIzIDcsMjBDIDcsMTkuNDQ3NyA3LjQ0NzcxLDE5IDgsMTkgWiAiLz4KPC9zdmc+Cg==',
    'cloudy': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE5QyAzLjIzODU4LDE5IDEsMTYuNzYxNCAxLDE0QyAxLDExLjIzOTIgMy4yMzc1OCw5LjAwMDk5IDUuOTk4MTcsOUMgNi45Nzc3Myw2LjY1MTA1IDkuMjk2MDUsNSAxMiw1QyAxNS40MzI4LDUgMTguMjQ0MSw3LjY2MTE1IDE4LjQ4MzUsMTEuMDMzTCAxOSwxMUMgMjEuMjA5MSwxMSAyMywxMi43OTA5IDIzLDE1QyAyMywxNy4yMDkxIDIxLjIwOTEsMTkgMTksMTlMIDYsMTkgWiBNIDE5LDEzTCAxNywxM0wgMTcsMTJDIDE3LDkuMjM4NTggMTQuNzYxNCw3IDEyLDdDIDkuNTEyODQsNyA3LjQ0OTgyLDguODE1OTkgNy4wNjQ1NiwxMS4xOTQ0QyA2LjczMzcyLDExLjA2ODggNi4zNzQ4OSwxMSA2LDExQyA0LjM0MzE1LDExIDMsMTIuMzQzMSAzLDE0QyAzLDE1LjY1NjkgNC4zNDMxNSwxNyA2LDE3TCAxOSwxN0MgMjAuMTA0NiwxNyAyMSwxNi4xMDQ2IDIxLDE1QyAyMSwxMy44OTU0IDIwLjEwNDYsMTMgMTksMTMgWiAiLz4KPC9zdmc+Cg==',
    'partly-cloudy-day': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSAxMi43NDExLDUuNDcxOTJDIDE1LjA5ODksNi41MjE2NiAxNi4zNTQzLDkuMDI2NDkgMTUuOTIwNywxMS40NThDIDE3LjE5NDEsMTIuNTU4MyAxOCwxNC4xODUgMTgsMTZMIDE3Ljk5NzYsMTYuMTcxNkMgMTguMzExMSwxNi4wNjA1IDE4LjY0ODUsMTYgMTksMTZDIDIwLjY1NjksMTYgMjIsMTcuMzQzMSAyMiwxOUMgMjIsMjAuNjU2OSAyMC42NTY5LDIyIDE5LDIyTCA2LDIyQyAzLjc5MDg2LDIyIDIsMjAuMjA5MSAyLDE4QyAyLDE1Ljc5MDkgMy43OTA4NiwxNCA2LDE0TCA2LjI3MjE2LDE0LjAxMTNDIDQuOTc5MiwxMi40NTIxIDQuNTk5OTQsMTAuMjM1MSA1LjQ3OTU4LDguMjU5MzdDIDYuNzE1MDcsNS40ODQ0MiA5Ljk2NjE4LDQuMjM2NDMgMTIuNzQxMSw1LjQ3MTkyIFogTSAxMS45Mjc3LDcuMjk5MDJDIDEwLjE2MTgsNi41MTI4IDguMDkyODksNy4zMDY5NyA3LjMwNjY3LDkuMDcyODVDIDYuODUxODgsMTAuMDk0MyA2LjkyNTg5LDExLjIxNzIgNy40MTA5MSwxMi4xMzQ1QyA4LjUxMTUzLDEwLjgyOTIgMTAuMTU4OSwxMCAxMiwxMEMgMTIuNzAxOCwxMCAxMy4zNzU1LDEwLjEyMDUgMTQuMDAxNCwxMC4zNDE5QyAxMy45NDM4LDkuMDU5NTQgMTMuMTgwMSw3Ljg1NjY2IDExLjkyNzcsNy4yOTkwMiBaIE0gMTMuNTU0NiwzLjY0NDg0QyAxMy4wMDc3LDMuNDAxMzcgMTIuNDQ3MywzLjIyODYyIDExLjg4MzYsMy4xMjI2NkwgMTQuMzY4MSwxLjgxNzc2TCAxNS4yNzQ4LDQuNzA2ODlDIDE0Ljc2MzksNC4yODYzOSAxNC4xODg1LDMuOTI3MDUgMTMuNTU0NiwzLjY0NDg0IFogTSA2LjA4OTAxLDQuNDM5OThDIDUuNjA0NzMsNC43OTE4MyA1LjE3NDkzLDUuMTkwNzggNC44MDEzMSw1LjYyNkwgNC45MTM0NSwyLjgyMTk0TCA3Ljg2ODg3LDMuNDgxMjhDIDcuMjQ5MjcsMy43MTM0NyA2LjY1MDM1LDQuMDMyMTQgNi4wODkwMSw0LjQzOTk4IFogTSAxNy45NzYsOS43MTI2N0MgMTcuOTEzNCw5LjExNzM0IDE3Ljc4MjgsOC41NDU2MyAxNy41OTI3LDguMDA0NDZMIDE5Ljk2NTEsOS41MDM2MUwgMTcuOTE2MywxMS43MzM0QyAxOC4wMjUxLDExLjA4MDcgMTguMDQ4NSwxMC40MDI3IDE3Ljk3Niw5LjcxMjY3IFogTSAzLjA0NDgyLDExLjMwMjlDIDMuMTA3NCwxMS44OTgzIDMuMjM4LDEyLjQ3IDMuNDI4MSwxMy4wMTExTCAxLjA1NTc4LDExLjUxMkwgMy4xMDQ0OSw5LjI4MjE5QyAyLjk5NTc3LDkuOTM0ODcgMi45NzIzLDEwLjYxMjkgMy4wNDQ4MiwxMS4zMDI5IFogTSAxOSwxOEwgMTYsMThMIDE2LDE2QyAxNiwxMy43OTA5IDE0LjIwOTEsMTIgMTIsMTJDIDkuNzkwODYsMTIgOCwxMy43OTA5IDgsMTZMIDYsMTZDIDQuODk1NDMsMTYgNCwxNi44OTU0IDQsMThDIDQsMTkuMTA0NiA0Ljg5NTQzLDIwIDYsMjBMIDE5LDIwQyAxOS41NTIzLDIwIDIwLDE5LjU1MjMgMjAsMTlDIDIwLDE4LjQ0NzcgMTkuNTUyMywxOCAxOSwxOCBaICIvPgo8L3N2Zz4K',
    'partly-cloudy-night': 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE5QyAzLjIzODU4LDE5IDEsMTYuNzYxNCAxLDE0QyAxLDExLjIzOTIgMy4yMzc1OCw5LjAwMDk5IDUuOTk4MTcsOUMgNi45Nzc3Myw2LjY1MTA1IDkuMjk2MDUsNSAxMiw1QyAxNS40MzI4LDUgMTguMjQ0MSw3LjY2MTE1IDE4LjQ4MzUsMTEuMDMzTCAxOSwxMUMgMjEuMjA5MSwxMSAyMywxMi43OTA5IDIzLDE1QyAyMywxNy4yMDkxIDIxLjIwOTEsMTkgMTksMTlMIDYsMTkgWiBNIDE5LDEzTCAxNywxM0wgMTcsMTJDIDE3LDkuMjM4NTggMTQuNzYxNCw3IDEyLDdDIDkuNTEyODQsNyA3LjQ0OTgyLDguODE1OTkgNy4wNjQ1NiwxMS4xOTQ0QyA2LjczMzcyLDExLjA2ODggNi4zNzQ4OSwxMSA2LDExQyA0LjM0MzE1LDExIDMsMTIuMzQzMSAzLDE0QyAzLDE1LjY1NjkgNC4zNDMxNSwxNyA2LDE3TCAxOSwxN0MgMjAuMTA0NiwxNyAyMSwxNi4xMDQ2IDIxLDE1QyAyMSwxMy44OTU0IDIwLjEwNDYsMTMgMTksMTMgWiAiLz4KPC9zdmc+Cg==',
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNITS): vol.In(['auto', 'si', 'us', 'ca', 'uk', 'uk2']),
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=120)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
    vol.Optional(CONF_FORECAST):
        vol.All(cv.ensure_list, [vol.Range(min=1, max=7)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dark Sky sensor."""
    # Validate the configuration
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    if CONF_UNITS in config:
        units = config[CONF_UNITS]
    elif hass.config.units.is_metric:
        units = 'si'
    else:
        units = 'us'

    forecast_data = DarkSkyData(
        api_key=config.get(CONF_API_KEY, None),
        latitude=hass.config.latitude,
        longitude=hass.config.longitude,
        units=units,
        interval=config.get(CONF_UPDATE_INTERVAL))
    forecast_data.update()
    forecast_data.update_currently()

    # If connection failed don't setup platform.
    if forecast_data.data is None:
        return False

    name = config.get(CONF_NAME)

    forecast = config.get(CONF_FORECAST)
    sensors = []
    for variable in config[CONF_MONITORED_CONDITIONS]:
        sensors.append(DarkSkySensor(forecast_data, variable, name))
        if forecast is not None and 'daily' in SENSOR_TYPES[variable][7]:
            for forecast_day in forecast:
                sensors.append(DarkSkySensor(forecast_data,
                                             variable, name, forecast_day))

    add_devices(sensors, True)


class DarkSkySensor(Entity):
    """Implementation of a Dark Sky sensor."""

    def __init__(self, forecast_data, sensor_type, name, forecast_day=0):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.forecast_data = forecast_data
        self.type = sensor_type
        self.forecast_day = forecast_day
        self._state = None
        self._icon = None
        self._unit_of_measurement = None

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.forecast_day == 0:
            return '{} {}'.format(self.client_name, self._name)
        else:
            return '{} {} {}'.format(self.client_name, self._name,
                                     self.forecast_day)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unit_system(self):
        """Return the unit system of this entity."""
        return self.forecast_data.unit_system

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        if self._icon is None or "summary" not in self.type:
            return None

        if self._icon in CONDITION_PICTURES:
            return CONDITION_PICTURES[self._icon]
        else:
            return None

    def update_unit_of_measurement(self):
        """Update units based on unit system."""
        unit_index = {
            'si': 1,
            'us': 2,
            'ca': 3,
            'uk': 4,
            'uk2': 5
        }.get(self.unit_system, 1)
        self._unit_of_measurement = SENSOR_TYPES[self.type][unit_index]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][6]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    def update(self):
        """Get the latest data from Dark Sky and updates the states."""
        # Call the API for new forecast data. Each sensor will re-trigger this
        # same exact call, but that's fine. We cache results for a short period
        # of time to prevent hitting API limits. Note that Dark Sky will
        # charge users for too many calls in 1 day, so take care when updating.
        self.forecast_data.update()
        self.update_unit_of_measurement()

        if self.type == 'minutely_summary':
            self.forecast_data.update_minutely()
            minutely = self.forecast_data.data_minutely
            self._state = getattr(minutely, 'summary', '')
            self._icon = getattr(minutely, 'icon', '')
        elif self.type == 'hourly_summary':
            self.forecast_data.update_hourly()
            hourly = self.forecast_data.data_hourly
            self._state = getattr(hourly, 'summary', '')
            self._icon = getattr(hourly, 'icon', '')
        elif self.forecast_day > 0 or (
                self.type in ['daily_summary',
                              'temperature_min',
                              'temperature_max',
                              'apparent_temperature_min',
                              'apparent_temperature_max',
                              'precip_intensity_max']):
            self.forecast_data.update_daily()
            daily = self.forecast_data.data_daily
            if self.type == 'daily_summary':
                self._state = getattr(daily, 'summary', '')
                self._icon = getattr(daily, 'icon', '')
            else:
                if hasattr(daily, 'data'):
                    self._state = self.get_state(
                        daily.data[self.forecast_day])
                else:
                    self._state = 0
        else:
            self.forecast_data.update_currently()
            currently = self.forecast_data.data_currently
            self._state = self.get_state(currently)

    def get_state(self, data):
        """
        Helper function that returns a new state based on the type.

        If the sensor type is unknown, the current state is returned.
        """
        lookup_type = convert_to_camel(self.type)
        state = getattr(data, lookup_type, None)

        if state is None:
            return state

        if "summary" in self.type:
            self._icon = getattr(data, 'icon', '')

        # Some state data needs to be rounded to whole values or converted to
        # percentages
        if self.type in ['precip_probability', 'cloud_cover', 'humidity']:
            return round(state * 100, 1)
        elif (self.type in ['dew_point', 'temperature', 'apparent_temperature',
                            'temperature_min', 'temperature_max',
                            'apparent_temperature_min',
                            'apparent_temperature_max',
                            'pressure', 'ozone']):
            return round(state, 1)
        return state


def convert_to_camel(data):
    """
    Convert snake case (foo_bar_bat) to camel case (fooBarBat).

    This is not pythonic, but needed for certain situations
    """
    components = data.split('_')
    return components[0] + "".join(x.title() for x in components[1:])


class DarkSkyData(object):
    """Get the latest data from Darksky."""

    def __init__(self, api_key, latitude, longitude, units, interval):
        """Initialize the data object."""
        self._api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.units = units

        self.data = None
        self.unit_system = None
        self.data_currently = None
        self.data_minutely = None
        self.data_hourly = None
        self.data_daily = None

        # Apply throttling to methods using configured interval
        self.update = Throttle(interval)(self._update)
        self.update_currently = Throttle(interval)(self._update_currently)
        self.update_minutely = Throttle(interval)(self._update_minutely)
        self.update_hourly = Throttle(interval)(self._update_hourly)
        self.update_daily = Throttle(interval)(self._update_daily)

    def _update(self):
        """Get the latest data from Dark Sky."""
        import forecastio

        try:
            self.data = forecastio.load_forecast(
                self._api_key, self.latitude, self.longitude, units=self.units)
        except (ConnectError, HTTPError, Timeout, ValueError) as error:
            _LOGGER.error("Unable to connect to Dark Sky. %s", error)
            self.data = None
        self.unit_system = self.data and self.data.json['flags']['units']

    def _update_currently(self):
        """Update currently data."""
        self.data_currently = self.data and self.data.currently()

    def _update_minutely(self):
        """Update minutely data."""
        self.data_minutely = self.data and self.data.minutely()

    def _update_hourly(self):
        """Update hourly data."""
        self.data_hourly = self.data and self.data.hourly()

    def _update_daily(self):
        """Update daily data."""
        self.data_daily = self.data and self.data.daily()
