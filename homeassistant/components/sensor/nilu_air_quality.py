"""
Sensor for checking the air quality around Norway.

Data delivered by luftkvalitet.info and nilu.no.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nilu_air_quality/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_UNIT_OF_MEASUREMENT, CONF_LATITUDE, CONF_LONGITUDE,
    CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_SHOW_ON_MAP)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['niluclient==0.1.1']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)

ICON = 'mdi:cloud-outline'

CONF_AREA = 'area'
CONF_STATION = 'station'
DEFAULT_NAME = 'NILU'

CONF_ATTRIBUTION = "Data provided by luftkvalitet.info and nilu.no"

ATTR_POLLUTION_INDEX = "pollution_index"
ATTR_MAX_POLLUTION_INDEX = 'max_pollution_index'
ATTR_AREA = "area"

CONF_ALLOWED_AREAS = [
    'Ålesund',
    'Zeppelinfjellet',
    'Tustervatn',
    'Trondheim',
    'Tromsø',
    'Sør-Varanger',
    'Stavanger',
    'Sarpsborg',
    'Sandve',
    'Prestebakke',
    'Oslo',
    'Narvik',
    'Moss',
    'Mo i Rana',
    'Lørenskog',
    'Lillestrøm',
    'Lillesand',
    'Lillehammer',
    'Kårvatn',
    'Kristiansand',
    'Karasjok',
    'Hurdal',
    'Harstad',
    'Hamar',
    'Halden',
    'Grenland',
    'Gjøvik',
    'Fredrikstad',
    'Elverum',
    'Drammen',
    'Bærum',
    'Brumunddal',
    'Bodø',
    'Birkenes',
    'Bergen'
]

CONF_ALLOWED_MEASURABLE_COMPONENTS = [
    'index',
    'PM1',
    'PM10',
    'PM2.5',
    'NO',
    'NO2',
    'NOx',
    'O3',
    'CO',
    'SO2'
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(CONF_ALLOWED_MEASURABLE_COMPONENTS)]),
    vol.Exclusive(CONF_AREA, 'station_collection',
                  'Can only configure one specific station or '
                  'stations in a specific area pr sensor. '
                  'Please only configure station or area.'):
        vol.All(cv.string, vol.In(CONF_ALLOWED_AREAS)),
    vol.Exclusive(CONF_STATION, 'station_collection',
                  'Can only configure one specific station or '
                  'stations in a specific area pr sensor. '
                  'Please only configure station or area.'):
        cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NILU air quality sensors."""
    import niluclient as nilu
    name = config.get(CONF_NAME)
    area = config.get(CONF_AREA)
    station = config.get(CONF_STATION)
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    show_on_map = config.get(CONF_SHOW_ON_MAP)

    sensors = []

    if station:
        stations = [station]
    elif area:
        stations = nilu.lookup_stations_in_area(area)
    else:
        latitude = config.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
        location_client = nilu.create_location_client(latitude, longitude)
        stations = location_client.station_names

    for station in stations:
        client = NiluData(nilu.create_station_client(station))
        client.update()
        for condition in monitored_conditions:
            if condition in client.data.sensors or condition == 'index':
                sensors.append(
                    NiluSensor(client, name, condition, show_on_map))
            else:
                _LOGGER.warning(
                    "%s doesn't seem to be measured on %s station.",
                    condition, station)

    add_entities(sensors, True)


class NiluData:
    """Class for handling the data retrieval."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api

    @property
    def data(self):
        """Get data cached in client."""
        return self.api.data

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from nilu apis."""
        self.api.update()


class NiluSensor(Entity):
    """Single nilu station air sensor."""

    def __init__(self,
                 api_data: NiluData,
                 name: str,
                 condition: str,
                 show_on_map: bool):
        """Initialize the sensor."""
        self._api = api_data
        self._name = "{} {} {}".format(name, api_data.data.name, condition)
        self._condition = condition
        self._state = None
        self._unit_of_measurement = None
        self._attrs = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }

        if show_on_map:
            self._attrs[CONF_LATITUDE] = api_data.data.latitude
            self._attrs[CONF_LONGITUDE] = api_data.data.longitude

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return ICON

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self) -> dict:
        """Return other details about the sensor state."""
        return self._attrs

    def update(self) -> None:
        """Update the sensor."""
        import niluclient as nilu
        self._api.update()

        if self._condition == 'index':
            sensors = self._api.data.sensors.values()
            max_index = max([s.pollution_index for s in sensors])
            self._state = nilu.POLLUTION_INDEX[max_index]

            self._attrs[ATTR_MAX_POLLUTION_INDEX] = max_index
            self._attrs[ATTR_AREA] = self._api.data.area

            for sensor in sensors:
                attr_name = sensor.component
                attr_unit = "{}_{}".format(attr_name, ATTR_UNIT_OF_MEASUREMENT)
                attr_index = "{}_{}".format(attr_name, ATTR_POLLUTION_INDEX)
                self._attrs[attr_name] = "{0:.2f}".format(sensor.value)
                self._attrs[attr_unit] = sensor.unit_of_measurement
                self._attrs[attr_index] = sensor.pollution_index
        else:
            sensor = self._api.data.sensors[self._condition]
            self._state = "{0:.2f}".format(sensor.value)
            self._unit_of_measurement = sensor.unit_of_measurement
            self._attrs[CONF_AREA] = self._api.data.area
            self._attrs[ATTR_POLLUTION_INDEX] = sensor.pollution_index
