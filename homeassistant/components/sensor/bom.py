"""
Support for Australian BOM (Bureau of Meteorology) weather service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bom/
"""
import datetime
import ftplib
import gzip
import io
import json
import logging
import os
import re
import xml.etree.ElementTree
import zipfile

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, TEMP_CELSIUS, CONF_NAME, ATTR_ATTRIBUTION,
    CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_FIND_QUERY = ("./forecast/area[@type='location']"
               "/forecast-period[@index='{}']/*[@type='{}']")
_FIND_QUERY_2 = ("./forecast/area[@type='metropolitan']"
                 "/forecast-period[@index='{}']/text[@type='forecast']")
_RESOURCE = 'http://www.bom.gov.au/fwo/{}/{}.{}.json'
_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = 'last_update'
ATTR_SENSOR_ID = 'sensor_id'
ATTR_STATION_ID = 'station_id'
ATTR_STATION_NAME = 'station_name'
ATTR_ZONE_ID = 'zone_id'

ATTR_ICON = 'icon'
ATTR_ISSUE_TIME = 'issue_time_local'
ATTR_PRODUCT_ID = 'product_id'
ATTR_PRODUCT_LOCATION = 'product_location'
ATTR_START_TIME = 'start_time_local'


CONF_ATTRIBUTION = "Data provided by the Australian Bureau of Meteorology"
CONF_FORECAST_DAYS = 'forecast_days'
CONF_FORECAST_PRODUCT_ID = 'product_id'
CONF_FORECAST_REST_OF_TODAY = 'rest_of_today'
CONF_FORECAST_CONDITIONS = 'forecast_conditions'
CONF_STATION = 'station'
CONF_ZONE_ID = 'zone_id'
CONF_WMO_ID = 'wmo_id'

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=35)

FORECAST_ICON_MAPPING = {
    '1': 'mdi:weather-sunny',
    '2': 'mdi:weather-night',
    '3': 'mdi:weather-partlycloudy',
    '4': 'mdi:weather-cloudy',
    '6': 'mdi:weather-sunset',
    '8': 'mdi:weather-rainy',
    '9': 'mdi:weather-windy',
    '10': 'mdi:weather-sunset',
    '11': 'mdi:weather-rainy',
    '12': 'mdi:weather-pouring',
    '13': 'mdi:weather-sunset',
    '14': 'mdi:weather-snowy',
    '15': 'mdi:weather-snowy',
    '16': 'mdi:weather-lightning',
    '17': 'mdi:weather-rainy'
}

FORECAST_SENSOR_TYPES = {
    'max': ['air_temperature_maximum', 'Max Temp C', TEMP_CELSIUS,
            'mdi:thermometer'],
    'min': ['air_temperature_minimum', 'Min Temp C', TEMP_CELSIUS,
            'mdi:thermometer'],
    'chance_of_rain': ['probability_of_precipitation', 'Chance of Rain', '%',
                       'mdi:water-percent'],
    'possible_rainfall': ['precipitation_range', 'Possible Rainfall', 'mm',
                          'mdi:water'],
    'summary': ['precis', 'Summary', None, 'mdi:text'],
    'detailed_summary': ['forecast', 'Detailed Summary', None, 'mdi:text'],
    'icon': ['forecast_icon_code', 'Icon', None, 'mdi:text']
}

PRODUCT_ID_LAT_LON = {
    'IDD10150': [-12.47, 130.85, 'Darwin', 'City'],
    'IDN10035': [-35.31, 149.20, 'Canberra', 'City'],
    'IDN10064': [-33.86, 151.21, 'Sydney', 'City'],
    'IDN11051': [-32.89, 151.71, 'Newcastle', 'City'],
    'IDN11052': [-33.44, 151.36, 'Central Coast', 'City'],
    'IDN11053': [-34.56, 150.79, 'Wollongong', 'City'],
    'IDN11055': [-36.49, 148.29, 'Alpine Centres', 'City'],
    'IDQ10095': [-27.48, 153.04, 'Brisbane', 'City'],
    'IDQ10610': [-27.94, 153.43, 'Gold Coast', 'City'],
    'IDQ10611': [-26.60, 153.09, 'Sunshine Coast', 'City'],
    'IDS10034': [-34.93, 138.58, 'Adelaide', 'City'],
    'IDT13600': [-42.89, 147.33, 'Hobart', 'City'],
    'IDT13610': [-41.42, 147.12, 'Launceston', 'City'],
    'IDV10450': [-37.83, 144.98, 'Melbourne', 'City'],
    'IDV10701': [-38.17, 144.38, 'Geelong', 'City'],
    'IDV10702': [-38.31, 145.00, 'Mornington Peninsula', 'City'],
    'IDW12300': [-31.92, 115.87, 'Perth', 'City'],
    'IDD10161': [-23.70, 133.88, 'Alice Springs', 'Town'],
    'IDD10199': [-12.18, 136.78, 'Nhulunbuy', 'Town'],
    'IDD10200': [-14.47, 132.26, 'Katherine', 'Town'],
    'IDD10201': [-25.24, 130.99, 'Yulara', 'Town'],
    'IDD10202': [-12.67, 132.84, 'Jabiru', 'Town'],
    'IDD10203': [-19.56, 134.22, 'Tennant Creek', 'Town'],
    'IDD10204': [-14.24, 129.52, 'Wadeye', 'Town'],
    'IDD10205': [-12.05, 134.23, 'Maningrida', 'Town'],
    'IDD10206': [-12.49, 130.99, 'Palmerston', 'Town'],
    'IDD10209': [-11.76, 130.63, 'Wurrimiyanga', 'Town'],
    'IDN11101': [-30.51, 151.67, 'Armidale', 'Town'],
    'IDN11102': [-35.71, 150.18, 'Batemans Bay', 'Town'],
    'IDN11103': [-31.97, 141.45, 'Broken Hill', 'Town'],
    'IDN11104': [-31.50, 145.83, 'Cobar', 'Town'],
    'IDN11105': [-30.17, 153.00, 'Coffs Harbour', 'Town'],
    'IDN11106': [-32.25, 148.60, 'Dubbo', 'Town'],
    'IDN11107': [-34.75, 149.72, 'Goulburn', 'Town'],
    'IDN11108': [-34.29, 146.06, 'Griffith', 'Town'],
    'IDN11109': [-33.71, 150.31, 'Katoomba', 'Town'],
    'IDN11110': [-28.79, 153.27, 'Lismore', 'Town'],
    'IDN11111': [-33.28, 149.10, 'Orange', 'Town'],
    'IDN11112': [-31.43, 152.91, 'Port Macquarie', 'Town'],
    'IDN11113': [-30.92, 150.91, 'Tamworth', 'Town'],
    'IDN11114': [-35.12, 147.37, 'Wagga Wagga', 'Town'],
    'IDN11116': [-34.48, 150.42, 'Bowral', 'Town'],
    'IDN11117': [-31.91, 152.46, 'Taree', 'Town'],
    'IDN11118': [-36.68, 149.84, 'Bega', 'Town'],
    'IDN11119': [-36.24, 149.13, 'Cooma', 'Town'],
    'IDN11121': [-28.18, 153.55, 'Tweed Heads', 'Town'],
    'IDQ10900': [-25.90, 139.35, 'Birdsville', 'Town'],
    'IDQ10901': [-24.87, 152.35, 'Bundaberg', 'Town'],
    'IDQ10902': [-16.92, 145.77, 'Cairns', 'Town'],
    'IDQ10903': [-26.41, 146.24, 'Charleville', 'Town'],
    'IDQ10904': [-20.07, 146.27, 'Charters Towers', 'Town'],
    'IDQ10906': [-23.53, 148.16, 'Emerald', 'Town'],
    'IDQ10907': [-23.84, 151.26, 'Gladstone', 'Town'],
    'IDQ10908': [-28.55, 150.31, 'Goondiwindi', 'Town'],
    'IDQ10909': [-26.20, 152.66, 'Gympie', 'Town'],
    'IDQ10910': [-25.30, 152.85, 'Hervey Bay', 'Town'],
    'IDQ10911': [-27.62, 152.76, 'Ipswich', 'Town'],
    'IDQ10913': [-23.44, 144.26, 'Longreach', 'Town'],
    'IDQ10914': [-21.14, 149.19, 'Mackay', 'Town'],
    'IDQ10915': [-25.54, 152.70, 'Maryborough', 'Town'],
    'IDQ10916': [-20.73, 139.49, 'Mount Isa', 'Town'],
    'IDQ10918': [-23.38, 150.51, 'Rockhampton', 'Town'],
    'IDQ10919': [-26.57, 148.79, 'Roma', 'Town'],
    'IDQ10922': [-27.56, 151.95, 'Toowoomba', 'Town'],
    'IDQ10923': [-19.26, 146.82, 'Townsville', 'Town'],
    'IDQ10925': [-12.64, 141.87, 'Weipa', 'Town'],
    'IDS11001': [-33.04, 137.58, 'Whyalla', 'Town'],
    'IDS11002': [-34.72, 135.86, 'Port Lincoln', 'Town'],
    'IDS11003': [-34.17, 140.75, 'Renmark', 'Town'],
    'IDS11004': [-37.83, 140.78, 'Mount Gambier', 'Town'],
    'IDS11016': [-35.06, 138.86, 'Mount Barker', 'Town'],
    'IDT13501': [-41.05, 145.91, 'Burnie', 'Town'],
    'IDT13502': [-41.93, 147.50, 'Campbell Town', 'Town'],
    'IDT13503': [-41.18, 146.36, 'Devonport', 'Town'],
    'IDT13504': [-42.78, 147.06, 'New Norfolk', 'Town'],
    'IDT13505': [-42.08, 145.56, 'Queenstown', 'Town'],
    'IDT13506': [-41.16, 147.51, 'Scottsdale', 'Town'],
    'IDT13507': [-40.84, 145.13, 'Smithton', 'Town'],
    'IDT13508': [-41.32, 148.25, 'St Helens', 'Town'],
    'IDT13509': [-42.15, 145.33, 'Strahan', 'Town'],
    'IDT13510': [-42.12, 148.08, 'Swansea', 'Town'],
    'IDT13511': [-41.16, 146.17, 'Ulverstone', 'Town'],
    'IDV10703': [-36.12, 146.89, 'Albury/Wodonga', 'Town'],
    'IDV10704': [-37.83, 147.63, 'Bairnsdale', 'Town'],
    'IDV10705': [-37.56, 143.86, 'Ballarat', 'Town'],
    'IDV10706': [-36.76, 144.28, 'Bendigo', 'Town'],
    'IDV10707': [-38.34, 143.59, 'Colac', 'Town'],
    'IDV10708': [-36.13, 144.75, 'Echuca', 'Town'],
    'IDV10710': [-37.74, 142.02, 'Hamilton', 'Town'],
    'IDV10711': [-36.71, 142.20, 'Horsham', 'Town'],
    'IDV10712': [-38.18, 146.27, 'Latrobe Valley', 'Town'],
    'IDV10714': [-34.18, 142.16, 'Mildura', 'Town'],
    'IDV10715': [-37.15, 146.43, 'Mount Buller', 'Town'],
    'IDV10716': [-37.83, 145.35, 'Mount Dandenong', 'Town'],
    'IDV10717': [-36.98, 147.13, 'Mount Hotham', 'Town'],
    'IDV10718': [-37.70, 148.46, 'Orbost', 'Town'],
    'IDV10719': [-38.11, 147.06, 'Sale', 'Town'],
    'IDV10721': [-37.02, 145.14, 'Seymour', 'Town'],
    'IDV10722': [-36.38, 145.40, 'Shepparton', 'Town'],
    'IDV10723': [-35.34, 143.56, 'Swan Hill', 'Town'],
    'IDV10725': [-36.36, 146.32, 'Wangaratta', 'Town'],
    'IDV10726': [-38.38, 142.48, 'Warrnambool', 'Town'],
    'IDV10728': [-38.61, 145.59, 'Wonthaggi', 'Town'],
    'IDV10730': [-37.14, 145.20, 'Falls Creek', 'Town'],
    'IDW14101': [-17.96, 122.22, 'Broome', 'Town'],
    'IDW14102': [-20.31, 118.58, 'Port Hedland', 'Town'],
    'IDW14103': [-20.74, 116.85, 'Karratha', 'Town'],
    'IDW14104': [-23.36, 119.73, 'Newman', 'Town'],
    'IDW14105': [-21.93, 114.13, 'Exmouth', 'Town'],
    'IDW14106': [-24.88, 113.66, 'Carnarvon', 'Town'],
    'IDW14107': [-28.77, 114.61, 'Geraldton', 'Town'],
    'IDW14108': [-30.75, 121.47, 'Kalgoorlie', 'Town'],
    'IDW14109': [-33.33, 115.64, 'Bunbury', 'Town'],
    'IDW14110': [-35.02, 117.88, 'Albany', 'Town'],
    'IDW14111': [-33.86, 121.89, 'Esperance', 'Town'],
    'IDW14112': [-15.77, 128.74, 'Kununurra', 'Town'],
    'IDW14113': [-26.59, 118.50, 'Meekatharra', 'Town'],
    'IDW14114': [-32.53, 115.72, 'Mandurah', 'Town'],
    'IDW14115': [-33.64, 115.35, 'Busselton', 'Town']
}

SENSOR_TYPES = {
    'wmo': ['wmo', None],
    'name': ['Station Name', None],
    'history_product': ['Zone', None],
    'local_date_time': ['Local Time', None],
    'local_date_time_full': ['Local Time Full', None],
    'aifstime_utc': ['UTC Time Full', None],
    'lat': ['Lat', None],
    'lon': ['Long', None],
    'apparent_t': ['Feels Like C', TEMP_CELSIUS],
    'cloud': ['Cloud', None],
    'cloud_base_m': ['Cloud Base', None],
    'cloud_oktas': ['Cloud Oktas', None],
    'cloud_type_id': ['Cloud Type ID', None],
    'cloud_type': ['Cloud Type', None],
    'delta_t': ['Delta Temp C', TEMP_CELSIUS],
    'gust_kmh': ['Wind Gust kmh', 'km/h'],
    'gust_kt': ['Wind Gust kt', 'kt'],
    'air_temp': ['Air Temp C', TEMP_CELSIUS],
    'dewpt': ['Dew Point C', TEMP_CELSIUS],
    'press': ['Pressure mb', 'mbar'],
    'press_qnh': ['Pressure qnh', 'qnh'],
    'press_msl': ['Pressure msl', 'msl'],
    'press_tend': ['Pressure Tend', None],
    'rain_trace': ['Rain Today', 'mm'],
    'rel_hum': ['Relative Humidity', '%'],
    'sea_state': ['Sea State', None],
    'swell_dir_worded': ['Swell Direction', None],
    'swell_height': ['Swell Height', 'm'],
    'swell_period': ['Swell Period', None],
    'vis_km': ['Visability km', 'km'],
    'weather': ['Weather', None],
    'wind_dir': ['Wind Direction', None],
    'wind_spd_kmh': ['Wind Speed kmh', 'km/h'],
    'wind_spd_kt': ['Wind Speed kt', 'kt']
}


def validate_product_id(product_id):
    """Check that the Product ID is well-formed."""
    if product_id is None or not product_id:
        return product_id
    if not re.fullmatch(r'ID[A-Z]\d\d\d\d\d', product_id):
        raise vol.error.Invalid("Malformed Product ID")
    return product_id


def validate_station(station):
    """Check that the station ID is well-formed."""
    if station is None:
        return
    station = station.replace('.shtml', '')
    if not re.fullmatch(r'ID[A-Z]\d\d\d\d\d\.\d\d\d\d\d', station):
        raise vol.error.Invalid('Malformed station ID')
    return station


def validate_days(days):
    """Check that days is within bounds."""
    if days not in range(0, 7):
        raise vol.error.Invalid("Forecast Days is out of Range")
    return days

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_ZONE_ID, 'Deprecated partial station ID'): cv.string,
    vol.Inclusive(CONF_WMO_ID, 'Deprecated partial station ID'): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_STATION): validate_station,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_FORECAST_DAYS, default=0): validate_days,
    vol.Optional(CONF_FORECAST_PRODUCT_ID, default=''): validate_product_id,
    vol.Optional(CONF_FORECAST_REST_OF_TODAY, default=False): cv.boolean,
    vol.Optional(CONF_FORECAST_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(FORECAST_SENSOR_TYPES)]),
})

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the BOM sensor."""
    station = config.get(CONF_STATION)
    zone_id, wmo_id = config.get(CONF_ZONE_ID), config.get(CONF_WMO_ID)
    forecast_conditions = config.get(CONF_FORECAST_CONDITIONS)
    forecast_days = config.get(CONF_FORECAST_DAYS)
    forecast_product_id = config.get(CONF_FORECAST_PRODUCT_ID)
    forecast_rest_of_today = config.get(CONF_FORECAST_REST_OF_TODAY)

    if station is not None:
        if zone_id and wmo_id:
            _LOGGER.warning(
                "Using config %s, not %s and %s for BOM sensor",
                CONF_STATION, CONF_ZONE_ID, CONF_WMO_ID)
    elif zone_id and wmo_id:
        station = '{}.{}'.format(zone_id, wmo_id)
    else:
        station = closest_station(
            config.get(CONF_LATITUDE), config.get(CONF_LONGITUDE),
            hass.config.config_dir)
        if station is None:
            _LOGGER.error("Could not get BOM weather station from lat/lon")
            return

    bom_data = BOMCurrentData(hass, station)

    try:
        bom_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from BOM Current: %s", err)
        return

    add_entities([BOMCurrentSensor(bom_data, variable, config.get(CONF_NAME))
                  for variable in config[CONF_MONITORED_CONDITIONS]])

    if forecast_days or forecast_rest_of_today:
        if not forecast_product_id:
            forecast_product_id = closest_forecast_product_id(
                hass.config.latitude, hass.config.longitude)
            if forecast_product_id is None:
                _LOGGER.error("Could not get BOM Product ID from lat/lon")
                return

        bom_forecast_data = BOMForecastData(forecast_product_id)
        bom_forecast_data.update()

        if forecast_rest_of_today:
            start = 0
        else:
            start = 1

        for index in range(start, forecast_days+1):
            for condition in forecast_conditions:
                add_entities([BOMForecastSensor(bom_forecast_data, condition,
                    index, config.get(CONF_NAME), forecast_product_id)])


class BOMCurrentSensor(Entity):
    """Implementation of a BOM current sensor."""

    def __init__(self, bom_data, condition, stationname):
        """Initialize the sensor."""
        self.bom_data = bom_data
        self._condition = condition
        self.stationname = stationname

    @property
    def name(self):
        """Return the name of the sensor."""
        if self.stationname is None:
            return 'BOM {}'.format(SENSOR_TYPES[self._condition][0])

        return 'BOM {} {}'.format(
            self.stationname, SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.bom_data.get_reading(self._condition)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_LAST_UPDATE: datetime.datetime.strptime(
                str(self.bom_data.latest_data['local_date_time_full']),
                '%Y%m%d%H%M%S'),
            ATTR_SENSOR_ID: self._condition,
            ATTR_STATION_ID: self.bom_data.latest_data['wmo'],
            ATTR_STATION_NAME: self.bom_data.latest_data['name'],
            ATTR_ZONE_ID: self.bom_data.latest_data['history_product'],
        }

        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        self.bom_data.update()

class BOMCurrentData:
    """Get data from BOM."""

    def __init__(self, hass, station_id):
        """Initialize the data object."""
        self._hass = hass
        self._zone_id, self._wmo_id = station_id.split('.')
        self._data = None

    def _build_url(self):
        """Build the URL for the requests."""
        url = _RESOURCE.format(self._zone_id, self._zone_id, self._wmo_id)
        _LOGGER.debug("BOM URL: %s", url)
        return url

    @property
    def latest_data(self):
        """Return the latest data object."""
        if self._data:
            return self._data[0]
        return None

    def get_reading(self, condition):
        """Return the value for the given condition.

        BOM weather publishes condition readings for weather (and a few other
        conditions) at intervals throughout the day. To avoid a `-` value in
        the frontend for these conditions, we traverse the historical data
        for the latest value that is not `-`.

        Iterators are used in this method to avoid iterating needlessly
        iterating through the entire BOM provided dataset.
        """
        condition_readings = (entry[condition] for entry in self._data)
        return next((x for x in condition_readings if x != '-'), None)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from BOM."""
        try:
            result = requests.get(self._build_url(), timeout=10).json()
            self._data = result['observations']['data']
        except ValueError as err:
            _LOGGER.error("Check BOM %s", err.args)
            self._data = None
            raise

class BOMForecastSensor(Entity):
    """Implementation of a BOM forecast sensor."""

    def __init__(self, bom_forecast_data, condition, index, name, product_id):
        """Initialize the sensor."""
        self._bom_forecast_data = bom_forecast_data
        self._condition = condition
        self._index = index
        self._name = name
        self._product_id = product_id
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        if not self._name:
            return 'BOM {} {}'.format(
                FORECAST_SENSOR_TYPES[self._condition][1], self._index)
        return 'BOM {} {} {}'.format(self._name,
            FORECAST_SENSOR_TYPES[self._condition][1], self._index)

    @property
    def state(self):
        """Return the state of the sensor."""
        reading = self._bom_forecast_data.get_reading(
            self._condition, self._index)

        if  self._condition == 'chance_of_rain':
            return reading.replace('%', '')
        if  self._condition == 'possible_rainfall':
            return reading.replace(' mm', '')
        return reading

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attr = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_SENSOR_ID: self._condition,
            ATTR_ISSUE_TIME: self._bom_forecast_data.get_issue_time(),
            ATTR_PRODUCT_ID: self._product_id,
            ATTR_PRODUCT_LOCATION: PRODUCT_ID_LAT_LON[self._product_id][2],
            ATTR_START_TIME: self._bom_forecast_data.get_start_time(
                self._index),
            ATTR_ICON: FORECAST_SENSOR_TYPES[self._condition][3]
        }
        if self._name:
            attr[ATTR_STATION_NAME] = self._name

        return attr

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return FORECAST_SENSOR_TYPES[self._condition][2]

    def update(self):
        """Fetch new state data for the sensor."""
        self._bom_forecast_data.update()


class BOMForecastData:
    """Get data from BOM."""

    def __init__(self, product_id):
        """Initialize the data object."""
        self._product_id = product_id

    def get_reading(self, condition, index):
        """Return the value for the given condition."""
        if condition == 'detailed_summary':
            if PRODUCT_ID_LAT_LON[self._product_id][3] == 'City':
                return self._data.find(_FIND_QUERY_2.format(index)).text
            else:
                return self._data.find(_FIND_QUERY.format(index,
                                                          'forecast')).text

        find_query = (_FIND_QUERY.format(index,
                                         FORECAST_SENSOR_TYPES[condition][0]))
        state = self._data.find(find_query)
        if condition == 'icon':
            return FORECAST_ICON_MAPPING[state.text]
        if state is None:
            if condition == 'possible_rainfall':
                return '0 mm'
            return 'n/a'
        return state.text

    def get_issue_time(self):
        """Return the issue time of forecast."""
        issue_time = self._data.find("./amoc/issue-time-local")
        if issue_time is None:
            return 'n/a'
        else:
            return issue_time.text

    def get_start_time(self, index):
        """Return the start time of forecast."""
        return self._data.find("./forecast/area[@type='location']/"
                               "forecast-period[@index='{}']".format(
                                index)).get("start-time-local")

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest forecast data from BOM."""
        with io.BytesIO() as file_obj:
            with ftplib.FTP('ftp.bom.gov.au') as ftp:
                ftp.login()
                ftp.cwd('anon/gen/fwo/')
                ftp.retrbinary('RETR ' + self._product_id + '.xml',
                               file_obj.write)
            file_obj.seek(0)
            tree = xml.etree.ElementTree.parse(file_obj)
            self._data = tree.getroot()

def _get_bom_stations():
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    This function does several MB of internet requests, so please use the
    caching version to minimise latency and hit-count.
    """
    latlon = {}
    with io.BytesIO() as file_obj:
        with ftplib.FTP('ftp.bom.gov.au') as ftp:
            ftp.login()
            ftp.cwd('anon2/home/ncc/metadata/sitelists')
            ftp.retrbinary('RETR stations.zip', file_obj.write)
        file_obj.seek(0)
        with zipfile.ZipFile(file_obj) as zipped:
            with zipped.open('stations.txt') as station_txt:
                for _ in range(4):
                    station_txt.readline()  # skip header
                while True:
                    line = station_txt.readline().decode().strip()
                    if len(line) < 120:
                        break  # end while loop, ignoring any footer text
                    wmo, lat, lon = (line[a:b].strip() for a, b in
                                     [(128, 134), (70, 78), (79, 88)])
                    if wmo != '..':
                        latlon[wmo] = (float(lat), float(lon))
    zones = {}
    pattern = (r'<a href="/products/(?P<zone>ID[A-Z]\d\d\d\d\d)/'
               r'(?P=zone)\.(?P<wmo>\d\d\d\d\d).shtml">')
    for state in ('nsw', 'vic', 'qld', 'wa', 'tas', 'nt'):
        url = 'http://www.bom.gov.au/{0}/observations/{0}all.shtml'.format(
            state)
        for zone_id, wmo_id in re.findall(pattern, requests.get(url).text):
            zones[wmo_id] = zone_id
    return {'{}.{}'.format(zones[k], k): latlon[k]
            for k in set(latlon) & set(zones)}


def bom_stations(cache_dir):
    """Return {CONF_STATION: (lat, lon)} for all stations, for auto-config.

    Results from internet requests are cached as compressed JSON, making
    subsequent calls very much faster.
    """
    cache_file = os.path.join(cache_dir, '.bom-stations.json.gz')
    if not os.path.isfile(cache_file):
        stations = _get_bom_stations()
        with gzip.open(cache_file, 'wt') as cache:
            json.dump(stations, cache, sort_keys=True)
        return stations
    with gzip.open(cache_file, 'rt') as cache:
        return {k: tuple(v) for k, v in json.load(cache).items()}


def closest_station(lat, lon, cache_dir):
    """Return the ZONE_ID.WMO_ID of the closest station to our lat/lon."""
    if lat is None or lon is None or not os.path.isdir(cache_dir):
        return
    stations = bom_stations(cache_dir)

    def comparable_dist(wmo_id):
        """Create a psudeo-distance from latitude/longitude."""
        station_lat, station_lon = stations[wmo_id]
        return (lat - station_lat) ** 2 + (lon - station_lon) ** 2

    return min(stations, key=comparable_dist)


def closest_forecast_product_id(lat, lon):
    """Return the closest product ID to our lat/lon."""

    def comparable_dist(product_id):
        """Create a psudeo-distance from latitude/longitude."""
        product_id_lat = PRODUCT_ID_LAT_LON[product_id][0]
        product_id_lon = PRODUCT_ID_LAT_LON[product_id][1]
        return (lat - product_id_lat) ** 2 + (lon - product_id_lon) ** 2

    return min(PRODUCT_ID_LAT_LON, key=comparable_dist)
