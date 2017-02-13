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
    'clear-day': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZ'
                  'GluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8v'
                  'RFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3M'
                  'vU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3'
                  'd3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3L'
                  'nczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxl'
                  'PSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCA'
                  'yNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMD'
                  'AgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iI'
                  'zAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIg'
                  'c3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSAxMiw3QyAxNC43NjE0LDc'
                  'gMTcsOS4yMzg1OCAxNywxMkMgMTcsMTQuNzYxNCAxNC43NjE0LDE3IDEyLD'
                  'E3QyA5LjIzODU3LDE3IDcsMTQuNzYxNCA3LDEyQyA3LDkuMjM4NTggOS4yM'
                  'zg1Nyw3IDEyLDcgWiBNIDEyLDkuMDAwMDFDIDEwLjM0MzEsOS4wMDAwMSA5'
                  'LDEwLjM0MzIgOSwxMkMgOSwxMy42NTY5IDEwLjM0MzEsMTUgMTIsMTVDIDE'
                  'zLjY1NjgsMTUgMTUsMTMuNjU2OSAxNSwxMkMgMTUsMTAuMzQzMiAxMy42NT'
                  'Y4LDkuMDAwMDEgMTIsOS4wMDAwMSBaIE0gMTIsMi4wMDAwMkwgMTQuMzk0M'
                  'Sw1LjQyMDExQyAxMy42NDcxLDUuMTQ4MjggMTIuODQwOSw1LjAwMDAxIDEy'
                  'LDUuMDAwMDFDIDExLjE1OTEsNS4wMDAwMSAxMC4zNTI4LDUuMTQ4MjggOS4'
                  '2MDU5Myw1LjQyMDExTCAxMiwyLjAwMDAyIFogTSAzLjM0NDk1LDcuMDA5MD'
                  'JMIDcuNTAzODgsNi42NDU3NUMgNi44OTUwMSw3LjE1NjY4IDYuMzYzNDgsN'
                  'y43ODA3OSA1Ljk0MzAzLDguNTA5MDJDIDUuNTIyNTgsOS4yMzcyNiA1LjI0'
                  'Nzg2LDEwLjAwOTYgNS4xMDk4MSwxMC43OTI0TCAzLjM0NDk1LDcuMDA5MDI'
                  'gWiBNIDMuMzU1MzcsMTcuMDA5TCA1LjEyMDIyLDEzLjIyNTdDIDUuMjU4Mj'
                  'csMTQuMDA4NCA1LjUzMywxNC43ODA4IDUuOTUzNDQsMTUuNTA5QyA2LjM3M'
                  'zg5LDE2LjIzNzMgNi45MDU0MywxNi44NjE0IDcuNTE0MjksMTcuMzcyM0wg'
                  'My4zNTUzNywxNy4wMDkgWiBNIDIwLjY0Niw3LjAwMzgyTCAxOC44ODEyLDE'
                  'wLjc4NzJDIDE4Ljc0MzEsMTAuMDA0NCAxOC40Njg0LDkuMjMyMDUgMTguMD'
                  'Q3OSw4LjUwMzgyQyAxNy42Mjc1LDcuNzc1NTkgMTcuMDk2LDcuMTUxNDggM'
                  'TYuNDg3MSw2LjY0MDU0TCAyMC42NDYsNy4wMDM4MiBaIE0gMjAuNjM1Niwx'
                  'Ni45OTM0TCAxNi40NzY3LDE3LjM1NjdDIDE3LjA4NTUsMTYuODQ1NyAxNy4'
                  '2MTcxLDE2LjIyMTYgMTguMDM3NSwxNS40OTM0QyAxOC40NTgsMTQuNzY1Mi'
                  'AxOC43MzI3LDEzLjk5MjggMTguODcwNywxMy4yMUwgMjAuNjM1NiwxNi45O'
                  'TM0IFogTSAxMS45NzkyLDIxLjk3OTJMIDkuNTg1MDksMTguNTU5MUMgMTAu'
                  'MzMyLDE4LjgzMDkgMTEuMTM4MywxOC45NzkyIDExLjk3OTIsMTguOTc5MkM'
                  'gMTIuODIwMSwxOC45NzkyIDEzLjYyNjMsMTguODMwOSAxNC4zNzMyLDE4Lj'
                  'U1OTFMIDExLjk3OTIsMjEuOTc5MiBaICIvPgo8L3N2Zz4K'),
    'clear-night': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmN'
                    'vZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1cz'
                    'Qy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3Jhc'
                    'GhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaH'
                    'R0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHR'
                    'wOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJh'
                    'c2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZ'
                    'XdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im'
                    '5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgo'
                    'JPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJv'
                    'a2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iT'
                    'SAxNy43NTMzLDQuMDkwMTdMIDE1LjIyMDUsNi4wMzExNUwgMTYuMTI4Ny'
                    'w5LjA5MDE3TCAxMy41LDcuMjgxMTVMIDEwLjg3MTMsOS4wOTAxN0wgMTE'
                    'uNzc5NSw2LjAzMTE1TCA5LjI0Njc1LDQuMDkwMTdMIDEyLjQzNjcsNC4w'
                    'MDg2MUwgMTMuNSwxTCAxNC41NjMzLDQuMDA4NjFMIDE3Ljc1MzMsNC4wO'
                    'TAxNyBaIE0gMjEuMjUsMTAuOTk4TCAxOS42MTI0LDEyLjI1M0wgMjAuMT'
                    'k5NiwxNC4yMzA4TCAxOC41LDEzLjA2MTJMIDE2LjgwMDQsMTQuMjMwOEw'
                    'gMTcuMzg3NiwxMi4yNTNMIDE1Ljc1LDEwLjk5OEwgMTcuODEyNSwxMC45'
                    'NDUzTCAxOC41LDlMIDE5LjE4NzUsMTAuOTQ1M0wgMjEuMjUsMTAuOTk4I'
                    'FogTSAxOC45NzA4LDE1Ljk0NTFDIDE5LjgwMDksMTUuODY2MSAyMC42OT'
                    'M1LDE3LjA0NzkgMjAuMTU3NiwxNy43OTkxQyAxOS44MzkzLDE4LjI0NTM'
                    'gMTkuNDgsMTguNjcxMyAxOS4wNzk1LDE5LjA3MTdDIDE1LjE3NDMsMjIu'
                    'OTc2OSA4Ljg0MjY2LDIyLjk3NjkgNC45Mzc0MSwxOS4wNzE3QyAxLjAzM'
                    'jE3LDE1LjE2NjQgMS4wMzIxNyw4LjgzNDc3IDQuOTM3NDEsNC45Mjk1M0'
                    'MgNS4zMzc4Miw0LjUyOTEyIDUuNzYzNzMsNC4xNjk3NyA2LjIwOTkzLDM'
                    'uODUxNDdDIDYuOTYxMTgsMy4zMTU1NSA4LjE0MjkzLDQuMjA4MTkgOC4w'
                    'NjQwMiw1LjAzODNDIDcuNzkxNTUsNy45MDQ3IDguNzUyODIsMTAuODY2M'
                    'iAxMC45NDc4LDEzLjA2MTNDIDEzLjE0MjgsMTUuMjU2MyAxNi4xMDQ0LD'
                    'E2LjIxNzUgMTguOTcwOCwxNS45NDUxIFogTSAxNy4zMzQsMTcuOTcwN0M'
                    'gMTQuNDk1LDE3LjgwOTQgMTEuNzAyNSwxNi42NDQzIDkuNTMzNjEsMTQu'
                    'NDc1NUMgNy4zNjQ3MywxMi4zMDY2IDYuMTk5NjMsOS41MTQwMyA2LjAzO'
                    'DMzLDYuNjc1MUMgMy4yMzExOCw5LjgxNjM5IDMuMzM1NjEsMTQuNjQxNC'
                    'A2LjM1MTYzLDE3LjY1NzRDIDkuMzY3NjQsMjAuNjczNSAxNC4xOTI3LDI'
                    'wLjc3NzkgMTcuMzM0LDE3Ljk3MDcgWiAiLz4KPC9zdmc+Cg=='),
    'rain': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz'
             '0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRy'
             'AxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVE'
             'Qvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC'
             '9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIi'
             'B2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaW'
             'dodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm'
             '91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPg'
             'oJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2'
             'lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE0QyA2Lj'
             'U1MjI5LDE0IDcsMTQuNDQ3NyA3LDE1QyA3LDE1LjU1MjMgNi41NTIyOCwxNiA2LD'
             'E2QyAzLjIzODU4LDE2IDEsMTMuNzYxNCAxLDExQyAxLDguMjM5MTkgMy4yMzc1OC'
             'w2LjAwMDk5IDUuOTk4MTcsNkMgNi45Nzc3MywzLjY1MTA1IDkuMjk2MDUsMi4wMD'
             'AwMSAxMiwyLjAwMDAxQyAxNS40MzI4LDIuMDAwMDEgMTguMjQ0MSw0LjY2MTE1ID'
             'E4LjQ4MzUsOC4wMzMwNEwgMTksOEMgMjEuMjA5MSw4IDIzLDkuNzkwODYgMjMsMT'
             'JDIDIzLDE0LjIwOTEgMjEuMjA5MSwxNiAxOSwxNkwgMTgsMTZDIDE3LjQ0NzcsMT'
             'YgMTcsMTUuNTUyMyAxNywxNUMgMTcsMTQuNDQ3NyAxNy40NDc3LDE0IDE4LDE0TC'
             'AxOSwxNEMgMjAuMTA0NiwxNCAyMSwxMy4xMDQ2IDIxLDEyQyAyMSwxMC44OTU0ID'
             'IwLjEwNDYsMTAgMTksMTBMIDE3LDEwTCAxNyw5QyAxNyw2LjIzODU4IDE0Ljc2MT'
             'QsNCAxMiw0QyA5LjUxMjg0LDQgNy40NDk4Miw1LjgxNiA3LjA2NDU2LDguMTk0Mz'
             'dDIDYuNzMzNzIsOC4wNjg3NyA2LjM3NDg5LDggNiw4QyA0LjM0MzE1LDggMyw5Lj'
             'M0MzE1IDMsMTFDIDMsMTIuNjU2OSA0LjM0MzE1LDE0IDYsMTQgWiBNIDE0LjgyOD'
             'UsMTUuNjcxNEMgMTYuMzkwNSwxNy4yMzM0IDE2LjM5MDUsMTkuNTE2NSAxNC44Mj'
             'g1LDIxLjA3ODVDIDE0LjA0OCwyMS44NTk1IDEzLjAyMzksMjIgMTEuOTk5OSwyMk'
             'MgMTAuOTc1OSwyMiA5Ljk1MjM5LDIxLjg1OTUgOS4xNzE5LDIxLjA3ODVDIDcuNj'
             'A5MzcsMTkuNTE2NSA3LjYwOTM3LDE3LjIzMzkgOS4xNzE5LDE1LjY3MTRMIDEyLj'
             'AwMDUsMTAuOTk5NUwgMTQuODI4NSwxNS42NzE0IFogTSAxMy40MTQyLDE2LjY5Mk'
             'wgMTIuMDAwMiwxNC4yNDk5TCAxMC41ODU5LDE2LjY5MkMgOS44MDQ2MiwxNy41MD'
             'g3IDkuODA0NjIsMTguNzAxOCAxMC41ODU5LDE5LjUxODJDIDEwLjk3NjEsMTkuOT'
             'I2NSAxMS40ODc5LDE5Ljk5OTkgMTEuOTk5OSwxOS45OTk5QyAxMi41MTE5LDE5Lj'
             'k5OTkgMTMuMDIzOSwxOS45MjY1IDEzLjQxNDIsMTkuNTE4MkMgMTQuMTk1MiwxOC'
             '43MDE4IDE0LjE5NTIsMTcuNTA4NCAxMy40MTQyLDE2LjY5MiBaICIvPgo8L3N2Zz'
             '4K'),
    'snow': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz'
             '0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRy'
             'AxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVE'
             'Qvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC'
             '9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIi'
             'B2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaW'
             'dodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm'
             '91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPg'
             'oJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2'
             'lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE0QyA2Lj'
             'U1MjI5LDE0IDcsMTQuNDQ3NyA3LDE1QyA3LDE1LjU1MjMgNi41NTIyOCwxNiA2LD'
             'E2QyAzLjIzODU4LDE2IDEsMTMuNzYxNCAxLDExQyAxLDguMjM5MTkgMy4yMzc1OC'
             'w2LjAwMDk5IDUuOTk4MTcsNkMgNi45Nzc3MywzLjY1MTA1IDkuMjk2MDUsMi4wMD'
             'AwMSAxMiwyLjAwMDAxQyAxNS40MzI4LDIuMDAwMDEgMTguMjQ0MSw0LjY2MTE1ID'
             'E4LjQ4MzUsOC4wMzMwNEwgMTksOEMgMjEuMjA5MSw4IDIzLDkuNzkwODYgMjMsMT'
             'JDIDIzLDE0LjIwOTEgMjEuMjA5MSwxNiAxOSwxNkwgMTgsMTZDIDE3LjQ0NzcsMT'
             'YgMTcsMTUuNTUyMyAxNywxNUMgMTcsMTQuNDQ3NyAxNy40NDc3LDE0IDE4LDE0TC'
             'AxOSwxNEMgMjAuMTA0NiwxNCAyMSwxMy4xMDQ2IDIxLDEyQyAyMSwxMC44OTU0ID'
             'IwLjEwNDYsMTAgMTksMTBMIDE3LDEwTCAxNyw5QyAxNyw2LjIzODU4IDE0Ljc2MT'
             'QsNCAxMiw0QyA5LjUxMjg0LDQgNy40NDk4Miw1LjgxNiA3LjA2NDU2LDguMTk0Mz'
             'dDIDYuNzMzNzIsOC4wNjg3NyA2LjM3NDg5LDggNiw4QyA0LjM0MzE1LDggMyw5Lj'
             'M0MzE1IDMsMTFDIDMsMTIuNjU2OSA0LjM0MzE1LDE0IDYsMTQgWiBNIDcuODc3ND'
             'gsMTguMDY5NEwgMTAuMDY4MiwxNy40ODI0TCA4LjQ2NDQ3LDE1Ljg3ODdDIDguMD'
             'czOTUsMTUuNDg4MiA4LjA3Mzk1LDE0Ljg1NSA4LjQ2NDQ3LDE0LjQ2NDVDIDguOD'
             'U0OTksMTQuMDczOSA5LjQ4ODE2LDE0LjA3MzkgOS44Nzg2OCwxNC40NjQ1TCAxMS'
             '40ODI0LDE2LjA2ODFMIDEyLjA2OTMsMTMuODc3NUMgMTIuMjEyMywxMy4zNDQgMT'
             'IuNzYwNiwxMy4wMjc0IDEzLjI5NDEsMTMuMTcwNEMgMTMuODI3NiwxMy4zMTMzID'
             'E0LjE0NDEsMTMuODYxNyAxNC4wMDEyLDE0LjM5NTFMIDEzLjQxNDIsMTYuNTg1OE'
             'wgMTUuNjA0OSwxNS45OTg4QyAxNi4xMzgzLDE1Ljg1NTkgMTYuNjg2NywxNi4xNz'
             'I0IDE2LjgyOTYsMTYuNzA1OUMgMTYuOTcyNiwxNy4yMzk0IDE2LjY1NiwxNy43OD'
             'c3IDE2LjEyMjUsMTcuOTMwN0wgMTMuOTMxOSwxOC41MTc2TCAxNS41MzU1LDIwLj'
             'EyMTNDIDE1LjkyNjEsMjAuNTExOCAxNS45MjYxLDIxLjE0NSAxNS41MzU1LDIxLj'
             'UzNTVDIDE1LjE0NSwyMS45MjYxIDE0LjUxMTgsMjEuOTI2MSAxNC4xMjEzLDIxLj'
             'UzNTVMIDEyLjUxNzYsMTkuOTMxOEwgMTEuOTMwNiwyMi4xMjI1QyAxMS43ODc3LD'
             'IyLjY1NiAxMS4yMzk0LDIyLjk3MjYgMTAuNzA1OSwyMi44Mjk2QyAxMC4xNzI0LD'
             'IyLjY4NjcgOS44NTU4NSwyMi4xMzgzIDkuOTk4NzksMjEuNjA0OUwgMTAuNTg1OC'
             'wxOS40MTQyTCA4LjM5NTExLDIwLjAwMTJDIDcuODYxNjUsMjAuMTQ0MSA3LjMxMz'
             'MxLDE5LjgyNzYgNy4xNzAzNywxOS4yOTQxQyA3LjAyNzQzLDE4Ljc2MDYgNy4zND'
             'QwMSwxOC4yMTIzIDcuODc3NDgsMTguMDY5NCBaICIvPgo8L3N2Zz4K'),
    'sleet': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZ'
              'z0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNW'
              'RyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9'
              'EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMj'
              'AwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsa'
              'W5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQi'
              'IGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJ'
              'hY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2'
              'VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzd'
              'HJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2'
              'LDE0QyA2LjU1MjI5LDE0IDcsMTQuNDQ3NyA3LDE1QyA3LDE1LjU1MjMgNi41NTI'
              'yOCwxNiA2LDE2QyAzLjIzODU4LDE2IDEsMTMuNzYxNCAxLDExQyAxLDguMjM5MT'
              'kgMy4yMzc1OCw2LjAwMDk5IDUuOTk4MTcsNkMgNi45Nzc3MywzLjY1MTA1IDkuM'
              'jk2MDUsMi4wMDAwMSAxMiwyLjAwMDAxQyAxNS40MzI4LDIuMDAwMDEgMTguMjQ0'
              'MSw0LjY2MTE1IDE4LjQ4MzUsOC4wMzMwNEwgMTksOEMgMjEuMjA5MSw4IDIzLDk'
              'uNzkwODYgMjMsMTJDIDIzLDE0LjIwOTEgMjEuMjA5MSwxNiAxOSwxNkwgMTgsMT'
              'ZDIDE3LjQ0NzcsMTYgMTcsMTUuNTUyMyAxNywxNUMgMTcsMTQuNDQ3NyAxNy40N'
              'Dc3LDE0IDE4LDE0TCAxOSwxNEMgMjAuMTA0NiwxNCAyMSwxMy4xMDQ2IDIxLDEy'
              'QyAyMSwxMC44OTU0IDIwLjEwNDYsMTAgMTksMTBMIDE3LDEwTCAxNyw5QyAxNyw'
              '2LjIzODU4IDE0Ljc2MTQsNCAxMiw0QyA5LjUxMjg0LDQgNy40NDk4Miw1LjgxNi'
              'A3LjA2NDU2LDguMTk0MzdDIDYuNzMzNzIsOC4wNjg3NyA2LjM3NDg5LDggNiw4Q'
              'yA0LjM0MzE1LDggMyw5LjM0MzE1IDMsMTFDIDMsMTIuNjU2OSA0LjM0MzE1LDE0'
              'IDYsMTQgWiBNIDEwLDE4QyAxMS4xMDQ2LDE4IDEyLDE4Ljg5NTQgMTIsMjBDIDE'
              'yLDIxLjEwNDYgMTEuMTA0NiwyMiAxMCwyMkMgOC44OTU0MywyMiA4LDIxLjEwND'
              'YgOCwyMEMgOCwxOC44OTU0IDguODk1NDMsMTggMTAsMTggWiBNIDE0LjUsMTZDI'
              'DE1LjMyODQsMTYgMTYsMTYuNjcxNiAxNiwxNy41QyAxNiwxOC4zMjg0IDE1LjMy'
              'ODQsMTkgMTQuNSwxOUMgMTMuNjcxNiwxOSAxMywxOC4zMjg0IDEzLDE3LjVDIDE'
              'zLDE2LjY3MTYgMTMuNjcxNiwxNiAxNC41LDE2IFogTSAxMC41LDEyQyAxMS4zMj'
              'g0LDEyIDEyLDEyLjY3MTYgMTIsMTMuNUMgMTIsMTQuMzI4NCAxMS4zMjg0LDE1I'
              'DEwLjUsMTVDIDkuNjcxNTcsMTUgOSwxNC4zMjg0IDksMTMuNUMgOSwxMi42NzE2'
              'IDkuNjcxNTcsMTIgMTAuNSwxMiBaICIvPgo8L3N2Zz4K'),
    'wind': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz'
             '0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRy'
             'AxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVE'
             'Qvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC'
             '9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIi'
             'B2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaW'
             'dodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm'
             '91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPg'
             'oJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2'
             'lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA0LDEwQyAzLj'
             'Q0NzcxLDEwIDMsOS41NTIyOSAzLDlDIDMsOC40NDc3MiAzLjQ0NzcyLDggNCw4TC'
             'AxMiw4QyAxMy4xMDQ2LDggMTQsNy4xMDQ1NyAxNCw2QyAxNCw0Ljg5NTQzIDEzLj'
             'EwNDYsNCAxMiw0QyAxMS40NDc3LDQgMTAuOTQ3Nyw0LjIyMzg2IDEwLjU4NTgsNC'
             '41ODU3OEMgMTAuMTk1Myw0Ljk3NjMxIDkuNTYyMDksNC45NzYzMSA5LjE3MTU3LD'
             'QuNTg1NzhDIDguNzgxMDQsNC4xOTUyNiA4Ljc4MTA0LDMuNTYyMDkgOS4xNzE1Ny'
             'wzLjE3MTU3QyA5Ljg5NTQzLDIuNDQ3NzIgMTAuODk1NCwyLjAwMDAxIDEyLDIuMD'
             'AwMDFDIDE0LjIwOTEsMi4wMDAwMSAxNiwzLjc5MDg2IDE2LDZDIDE2LDguMjA5MT'
             'QgMTQuMjA5MSwxMCAxMiwxMEwgNCwxMCBaIE0gMTksMTJDIDE5LjU1MjMsMTIgMj'
             'AsMTEuNTUyMyAyMCwxMUMgMjAsMTAuNDQ3NyAxOS41NTIzLDEwIDE5LDEwQyAxOC'
             '43MjM4LDEwIDE4LjQ3MzgsMTAuMTExOSAxOC4yOTI5LDEwLjI5MjlDIDE3LjkwMj'
             'QsMTAuNjgzNCAxNy4yNjkyLDEwLjY4MzQgMTYuODc4NywxMC4yOTI5QyAxNi40OD'
             'gxLDkuOTAyMzcgMTYuNDg4Miw5LjI2OTIgMTYuODc4Nyw4Ljg3ODY4QyAxNy40Mj'
             'E2LDguMzM1NzkgMTguMTcxNiw4IDE5LDhDIDIwLjY1NjgsOCAyMiw5LjM0MzE1ID'
             'IyLDExQyAyMiwxMi42NTY5IDIwLjY1NjgsMTQgMTksMTRMIDUsMTRDIDQuNDQ3Nz'
             'EsMTQgNCwxMy41NTIzIDQsMTNDIDQsMTIuNDQ3NyA0LjQ0NzcyLDEyIDUsMTJMID'
             'E5LDEyIFogTSAxOCwxOEwgNCwxOEMgMy40NDc3MiwxOCAzLDE3LjU1MjMgMywxN0'
             'MgMywxNi40NDc3IDMuNDQ3NzEsMTYgNCwxNkwgMTgsMTZDIDE5LjY1NjgsMTYgMj'
             'EsMTcuMzQzMSAyMSwxOUMgMjEsMjAuNjU2OSAxOS42NTY4LDIyIDE4LDIyQyAxNy'
             '4xNzE2LDIyIDE2LjQyMTYsMjEuNjY0MiAxNS44Nzg3LDIxLjEyMTNDIDE1LjQ4OD'
             'IsMjAuNzMwOCAxNS40ODgxLDIwLjA5NzYgMTUuODc4NywxOS43MDcxQyAxNi4yNj'
             'kyLDE5LjMxNjYgMTYuOTAyNCwxOS4zMTY2IDE3LjI5MjksMTkuNzA3MUMgMTcuND'
             'czOCwxOS44ODgxIDE3LjcyMzgsMjAgMTgsMjBDIDE4LjU1MjMsMjAgMTksMTkuNT'
             'UyMyAxOSwxOUMgMTksMTguNDQ3NyAxOC41NTIzLDE4IDE4LDE4IFogIi8+Cjwvc3'
             'ZnPgo='),
    'fog': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0'
            'idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIFNWRyAx'
            'LjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc'
            '3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdm'
            'ciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJ'
            'zaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0i'
            'MjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9I'
            'm5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUiPgoJPHBhdG'
            'ggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjI'
            'iIHN0cm9rZS1saW5lam9pbj0icm91bmQiIGQ9Ik0gMywxNUwgMTMsMTVDIDEzLjU1'
            'MjMsMTUgMTQsMTUuNDQ3NyAxNCwxNkMgMTQsMTYuNTUyMyAxMy41NTIzLDE3IDEzL'
            'DE3TCAzLDE3QyAyLjQ0NzcyLDE3IDIsMTYuNTUyMyAyLDE2QyAyLDE1LjQ0NzcgMi'
            '40NDc3MiwxNSAzLDE1IFogTSAxNiwxNUwgMjEsMTVDIDIxLjU1MjMsMTUgMjIsMTU'
            'uNDQ3NyAyMiwxNkMgMjIsMTYuNTUyMyAyMS41NTIzLDE3IDIxLDE3TCAxNiwxN0Mg'
            'MTUuNDQ3NywxNyAxNSwxNi41NTIzIDE1LDE2QyAxNSwxNS40NDc3IDE1LjQ0NzcsM'
            'TUgMTYsMTUgWiBNIDEsMTJDIDEsOS4yMzkxOSAzLjIzNzU5LDcuMDAxIDUuOTk4MT'
            'csN0MgNi45Nzc3Myw0LjY1MTA1IDkuMjk2MDUsMy4wMDAwMSAxMiwzLjAwMDAxQyA'
            'xNS40MzI4LDMuMDAwMDEgMTguMjQ0MSw1LjY2MTE1IDE4LjQ4MzUsOS4wMzMwNUwg'
            'MTksOUMgMjEuMTkyOCw5IDIyLjk3MzUsMTAuNzY0NSAyMi45OTk0LDEzTCAyMSwxM'
            '0MgMjEsMTEuODk1NCAyMC4xMDQ2LDExIDE5LDExTCAxNywxMUwgMTcsMTBDIDE3LD'
            'cuMjM4NTggMTQuNzYxNCw1LjAwMDAxIDEyLDUuMDAwMDFDIDkuNTEyODQsNS4wMDA'
            'wMSA3LjQ0OTgyLDYuODE2IDcuMDY0NTYsOS4xOTQzOEMgNi43MzM3Miw5LjA2ODc3'
            'IDYuMzc0ODksOS4wMDAwMSA2LDkuMDAwMDFDIDQuMzQzMTUsOS4wMDAwMSAzLDEwL'
            'jM0MzIgMywxMkMgMywxMi4zNTA2IDMuMDYwMTYsMTIuNjg3MiAzLjE3MDcxLDEzTC'
            'AxLjEwMDAyLDEzTCAxLDEyIFogTSAzLDE5TCA1LDE5QyA1LjU1MjI4LDE5IDYsMTk'
            'uNDQ3NyA2LDIwQyA2LDIwLjU1MjMgNS41NTIyOCwyMSA1LDIxTCAzLDIxQyAyLjQ0'
            'NzcyLDIxIDIsMjAuNTUyMyAyLDIwQyAyLDE5LjQ0NzcgMi40NDc3MiwxOSAzLDE5I'
            'FogTSA4LDE5TCAyMSwxOUMgMjEuNTUyMywxOSAyMiwxOS40NDc3IDIyLDIwQyAyMi'
            'wyMC41NTIzIDIxLjU1MjMsMjEgMjEsMjFMIDgsMjFDIDcuNDQ3NzEsMjEgNywyMC4'
            '1NTIzIDcsMjBDIDcsMTkuNDQ3NyA3LjQ0NzcxLDE5IDgsMTkgWiAiLz4KPC9zdmc+'
            'Cg=='),
    'cloudy': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGlu'
               'Zz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJMSUMgIi0vL1czQy8vRFREIF'
               'NWRyAxLjEvL0VOIiAiaHR0cDovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEu'
               'MS9EVEQvc3ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcm'
               'cvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5'
               'L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB3aWR0aD'
               '0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5h'
               'YmxlLWJhY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT'
               '0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5'
               'PSIxIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZC'
               'IgZD0iTSA2LDE5QyAzLjIzODU4LDE5IDEsMTYuNzYxNCAxLDE0QyAxLDExLjIz'
               'OTIgMy4yMzc1OCw5LjAwMDk5IDUuOTk4MTcsOUMgNi45Nzc3Myw2LjY1MTA1ID'
               'kuMjk2MDUsNSAxMiw1QyAxNS40MzI4LDUgMTguMjQ0MSw3LjY2MTE1IDE4LjQ4'
               'MzUsMTEuMDMzTCAxOSwxMUMgMjEuMjA5MSwxMSAyMywxMi43OTA5IDIzLDE1Qy'
               'AyMywxNy4yMDkxIDIxLjIwOTEsMTkgMTksMTlMIDYsMTkgWiBNIDE5LDEzTCAx'
               'NywxM0wgMTcsMTJDIDE3LDkuMjM4NTggMTQuNzYxNCw3IDEyLDdDIDkuNTEyOD'
               'QsNyA3LjQ0OTgyLDguODE1OTkgNy4wNjQ1NiwxMS4xOTQ0QyA2LjczMzcyLDEx'
               'LjA2ODggNi4zNzQ4OSwxMSA2LDExQyA0LjM0MzE1LDExIDMsMTIuMzQzMSAzLD'
               'E0QyAzLDE1LjY1NjkgNC4zNDMxNSwxNyA2LDE3TCAxOSwxN0MgMjAuMTA0Niwx'
               'NyAyMSwxNi4xMDQ2IDIxLDE1QyAyMSwxMy44OTU0IDIwLjEwNDYsMTMgMTksMT'
               'MgWiAiLz4KPC9zdmc+Cg=='),
    'partly-cloudy-day': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wI'
                          'iBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQVUJM'
                          'SUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0cDovL3d'
                          '3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3ZnMTEuZH'
                          'RkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwM'
                          'C9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8x'
                          'OTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJ'
                          'mdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9Ij'
                          'AgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJhY2tncm91bmQ9Im5ld'
                          'yAwIDAgMjQuMDAgMjQuMDAiIHhtbDpzcGFjZT0icHJlc2VydmUi'
                          'PgoJPHBhdGggZmlsbD0iIzAwMDAwMCIgZmlsbC1vcGFjaXR5PSI'
                          'xIiBzdHJva2Utd2lkdGg9IjAuMiIgc3Ryb2tlLWxpbmVqb2luPS'
                          'Jyb3VuZCIgZD0iTSAxMi43NDExLDUuNDcxOTJDIDE1LjA5ODksN'
                          'i41MjE2NiAxNi4zNTQzLDkuMDI2NDkgMTUuOTIwNywxMS40NThD'
                          'IDE3LjE5NDEsMTIuNTU4MyAxOCwxNC4xODUgMTgsMTZMIDE3Ljk'
                          '5NzYsMTYuMTcxNkMgMTguMzExMSwxNi4wNjA1IDE4LjY0ODUsMT'
                          'YgMTksMTZDIDIwLjY1NjksMTYgMjIsMTcuMzQzMSAyMiwxOUMgM'
                          'jIsMjAuNjU2OSAyMC42NTY5LDIyIDE5LDIyTCA2LDIyQyAzLjc5'
                          'MDg2LDIyIDIsMjAuMjA5MSAyLDE4QyAyLDE1Ljc5MDkgMy43OTA'
                          '4NiwxNCA2LDE0TCA2LjI3MjE2LDE0LjAxMTNDIDQuOTc5MiwxMi'
                          '40NTIxIDQuNTk5OTQsMTAuMjM1MSA1LjQ3OTU4LDguMjU5MzdDI'
                          'DYuNzE1MDcsNS40ODQ0MiA5Ljk2NjE4LDQuMjM2NDMgMTIuNzQx'
                          'MSw1LjQ3MTkyIFogTSAxMS45Mjc3LDcuMjk5MDJDIDEwLjE2MTg'
                          'sNi41MTI4IDguMDkyODksNy4zMDY5NyA3LjMwNjY3LDkuMDcyOD'
                          'VDIDYuODUxODgsMTAuMDk0MyA2LjkyNTg5LDExLjIxNzIgNy40M'
                          'TA5MSwxMi4xMzQ1QyA4LjUxMTUzLDEwLjgyOTIgMTAuMTU4OSwx'
                          'MCAxMiwxMEMgMTIuNzAxOCwxMCAxMy4zNzU1LDEwLjEyMDUgMTQ'
                          'uMDAxNCwxMC4zNDE5QyAxMy45NDM4LDkuMDU5NTQgMTMuMTgwMS'
                          'w3Ljg1NjY2IDExLjkyNzcsNy4yOTkwMiBaIE0gMTMuNTU0NiwzL'
                          'jY0NDg0QyAxMy4wMDc3LDMuNDAxMzcgMTIuNDQ3MywzLjIyODYy'
                          'IDExLjg4MzYsMy4xMjI2NkwgMTQuMzY4MSwxLjgxNzc2TCAxNS4'
                          'yNzQ4LDQuNzA2ODlDIDE0Ljc2MzksNC4yODYzOSAxNC4xODg1LD'
                          'MuOTI3MDUgMTMuNTU0NiwzLjY0NDg0IFogTSA2LjA4OTAxLDQuN'
                          'DM5OThDIDUuNjA0NzMsNC43OTE4MyA1LjE3NDkzLDUuMTkwNzgg'
                          'NC44MDEzMSw1LjYyNkwgNC45MTM0NSwyLjgyMTk0TCA3Ljg2ODg'
                          '3LDMuNDgxMjhDIDcuMjQ5MjcsMy43MTM0NyA2LjY1MDM1LDQuMD'
                          'MyMTQgNi4wODkwMSw0LjQzOTk4IFogTSAxNy45NzYsOS43MTI2N'
                          '0MgMTcuOTEzNCw5LjExNzM0IDE3Ljc4MjgsOC41NDU2MyAxNy41'
                          'OTI3LDguMDA0NDZMIDE5Ljk2NTEsOS41MDM2MUwgMTcuOTE2Myw'
                          'xMS43MzM0QyAxOC4wMjUxLDExLjA4MDcgMTguMDQ4NSwxMC40MD'
                          'I3IDE3Ljk3Niw5LjcxMjY3IFogTSAzLjA0NDgyLDExLjMwMjlDI'
                          'DMuMTA3NCwxMS44OTgzIDMuMjM4LDEyLjQ3IDMuNDI4MSwxMy4w'
                          'MTExTCAxLjA1NTc4LDExLjUxMkwgMy4xMDQ0OSw5LjI4MjE5QyA'
                          'yLjk5NTc3LDkuOTM0ODcgMi45NzIzLDEwLjYxMjkgMy4wNDQ4Mi'
                          'wxMS4zMDI5IFogTSAxOSwxOEwgMTYsMThMIDE2LDE2QyAxNiwxM'
                          'y43OTA5IDE0LjIwOTEsMTIgMTIsMTJDIDkuNzkwODYsMTIgOCwx'
                          'My43OTA5IDgsMTZMIDYsMTZDIDQuODk1NDMsMTYgNCwxNi44OTU'
                          '0IDQsMThDIDQsMTkuMTA0NiA0Ljg5NTQzLDIwIDYsMjBMIDE5LD'
                          'IwQyAxOS41NTIzLDIwIDIwLDE5LjU1MjMgMjAsMTlDIDIwLDE4L'
                          'jQ0NzcgMTkuNTUyMywxOCAxOSwxOCBaICIvPgo8L3N2Zz4K'),
    'partly-cloudy-night': ('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4'
                            'wIiBlbmNvZGluZz0idXRmLTgiPz4KPCFET0NUWVBFIHN2ZyBQ'
                            'VUJMSUMgIi0vL1czQy8vRFREIFNWRyAxLjEvL0VOIiAiaHR0c'
                            'DovL3d3dy53My5vcmcvR3JhcGhpY3MvU1ZHLzEuMS9EVEQvc3'
                            'ZnMTEuZHRkIj4KPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5'
                            'vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3'
                            'LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIGJhc'
                            '2VQcm9maWxlPSJmdWxsIiB3aWR0aD0iMjQiIGhlaWdodD0iMj'
                            'QiIHZpZXdCb3g9IjAgMCAyNC4wMCAyNC4wMCIgZW5hYmxlLWJ'
                            'hY2tncm91bmQ9Im5ldyAwIDAgMjQuMDAgMjQuMDAiIHhtbDpz'
                            'cGFjZT0icHJlc2VydmUiPgoJPHBhdGggZmlsbD0iIzAwMDAwM'
                            'CIgZmlsbC1vcGFjaXR5PSIxIiBzdHJva2Utd2lkdGg9IjAuMi'
                            'Igc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZD0iTSA2LDE5QyA'
                            'zLjIzODU4LDE5IDEsMTYuNzYxNCAxLDE0QyAxLDExLjIzOTIg'
                            'My4yMzc1OCw5LjAwMDk5IDUuOTk4MTcsOUMgNi45Nzc3Myw2L'
                            'jY1MTA1IDkuMjk2MDUsNSAxMiw1QyAxNS40MzI4LDUgMTguMj'
                            'Q0MSw3LjY2MTE1IDE4LjQ4MzUsMTEuMDMzTCAxOSwxMUMgMjE'
                            'uMjA5MSwxMSAyMywxMi43OTA5IDIzLDE1QyAyMywxNy4yMDkx'
                            'IDIxLjIwOTEsMTkgMTksMTlMIDYsMTkgWiBNIDE5LDEzTCAxN'
                            'ywxM0wgMTcsMTJDIDE3LDkuMjM4NTggMTQuNzYxNCw3IDEyLD'
                            'dDIDkuNTEyODQsNyA3LjQ0OTgyLDguODE1OTkgNy4wNjQ1Niw'
                            'xMS4xOTQ0QyA2LjczMzcyLDExLjA2ODggNi4zNzQ4OSwxMSA2'
                            'LDExQyA0LjM0MzE1LDExIDMsMTIuMzQzMSAzLDE0QyAzLDE1L'
                            'jY1NjkgNC4zNDMxNSwxNyA2LDE3TCAxOSwxN0MgMjAuMTA0Ni'
                            'wxNyAyMSwxNi4xMDQ2IDIxLDE1QyAyMSwxMy44OTU0IDIwLjE'
                            'wNDYsMTMgMTksMTMgWiAiLz4KPC9zdmc+Cg=='),
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
