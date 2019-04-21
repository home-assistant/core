"""
Sensor for checking the air quality around Norway.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/air_quality.nilu/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.air_quality import (
    PLATFORM_SCHEMA, AirQualityEntity)
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_SHOW_ON_MAP)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['niluclient==0.1.2']

_LOGGER = logging.getLogger(__name__)

ATTR_AREA = 'area'
ATTR_POLLUTION_INDEX = 'nilu_pollution_index'
ATTRIBUTION = "Data provided by luftkvalitet.info and nilu.no"

CONF_AREA = 'area'
CONF_STATION = 'stations'

DEFAULT_NAME = 'NILU'

SCAN_INTERVAL = timedelta(minutes=30)

CONF_ALLOWED_AREAS = [
    'Bergen',
    'Birkenes',
    'Bodø',
    'Brumunddal',
    'Bærum',
    'Drammen',
    'Elverum',
    'Fredrikstad',
    'Gjøvik',
    'Grenland',
    'Halden',
    'Hamar',
    'Harstad',
    'Hurdal',
    'Karasjok',
    'Kristiansand',
    'Kårvatn',
    'Lillehammer',
    'Lillesand',
    'Lillestrøm',
    'Lørenskog',
    'Mo i Rana',
    'Moss',
    'Narvik',
    'Oslo',
    'Prestebakke',
    'Sandve',
    'Sarpsborg',
    'Stavanger',
    'Sør-Varanger',
    'Tromsø',
    'Trondheim',
    'Tustervatn',
    'Zeppelinfjellet',
    'Ålesund',
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Exclusive(CONF_AREA, 'station_collection',
                  'Can only configure one specific station or '
                  'stations in a specific area pr sensor. '
                  'Please only configure station or area.'
                  ): vol.All(cv.string, vol.In(CONF_ALLOWED_AREAS)),
    vol.Exclusive(CONF_STATION, 'station_collection',
                  'Can only configure one specific station or '
                  'stations in a specific area pr sensor. '
                  'Please only configure station or area.'
                  ): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NILU air quality sensor."""
    import niluclient as nilu
    name = config.get(CONF_NAME)
    area = config.get(CONF_AREA)
    stations = config.get(CONF_STATION)
    show_on_map = config.get(CONF_SHOW_ON_MAP)

    sensors = []

    if area:
        stations = nilu.lookup_stations_in_area(area)
    elif not area and not stations:
        latitude = config.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
        location_client = nilu.create_location_client(latitude, longitude)
        stations = location_client.station_names

    for station in stations:
        client = NiluData(nilu.create_station_client(station))
        client.update()
        if client.data.sensors:
            sensors.append(NiluSensor(client, name, show_on_map))
        else:
            _LOGGER.warning("%s didn't give any sensors results", station)

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
        """Get the latest data from nilu API."""
        self.api.update()


class NiluSensor(AirQualityEntity):
    """Single nilu station air sensor."""

    def __init__(self, api_data: NiluData, name: str, show_on_map: bool):
        """Initialize the sensor."""
        self._api = api_data
        self._name = "{} {}".format(name, api_data.data.name)
        self._max_aqi = None
        self._attrs = {}

        if show_on_map:
            self._attrs[CONF_LATITUDE] = api_data.data.latitude
            self._attrs[CONF_LONGITUDE] = api_data.data.longitude

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def device_state_attributes(self) -> dict:
        """Return other details about the sensor state."""
        return self._attrs

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def air_quality_index(self) -> str:
        """Return the Air Quality Index (AQI)."""
        return self._max_aqi

    @property
    def carbon_monoxide(self) -> str:
        """Return the CO (carbon monoxide) level."""
        from niluclient import CO
        return self.get_component_state(CO)

    @property
    def carbon_dioxide(self) -> str:
        """Return the CO2 (carbon dioxide) level."""
        from niluclient import CO2
        return self.get_component_state(CO2)

    @property
    def nitrogen_oxide(self) -> str:
        """Return the N2O (nitrogen oxide) level."""
        from niluclient import NOX
        return self.get_component_state(NOX)

    @property
    def nitrogen_monoxide(self) -> str:
        """Return the NO (nitrogen monoxide) level."""
        from niluclient import NO
        return self.get_component_state(NO)

    @property
    def nitrogen_dioxide(self) -> str:
        """Return the NO2 (nitrogen dioxide) level."""
        from niluclient import NO2
        return self.get_component_state(NO2)

    @property
    def ozone(self) -> str:
        """Return the O3 (ozone) level."""
        from niluclient import OZONE
        return self.get_component_state(OZONE)

    @property
    def particulate_matter_2_5(self) -> str:
        """Return the particulate matter 2.5 level."""
        from niluclient import PM25
        return self.get_component_state(PM25)

    @property
    def particulate_matter_10(self) -> str:
        """Return the particulate matter 10 level."""
        from niluclient import PM10
        return self.get_component_state(PM10)

    @property
    def particulate_matter_0_1(self) -> str:
        """Return the particulate matter 0.1 level."""
        from niluclient import PM1
        return self.get_component_state(PM1)

    @property
    def sulphur_dioxide(self) -> str:
        """Return the SO2 (sulphur dioxide) level."""
        from niluclient import SO2
        return self.get_component_state(SO2)

    def get_component_state(self, component_name: str) -> str:
        """Return formatted value of specified component."""
        if component_name in self._api.data.sensors:
            sensor = self._api.data.sensors[component_name]
            return sensor.value
        return None

    def update(self) -> None:
        """Update the sensor."""
        import niluclient as nilu
        self._api.update()

        sensors = self._api.data.sensors.values()
        if sensors:
            max_index = max([s.pollution_index for s in sensors])
            self._max_aqi = max_index
            self._attrs[ATTR_POLLUTION_INDEX] = \
                nilu.POLLUTION_INDEX[self._max_aqi]

        self._attrs[ATTR_AREA] = self._api.data.area
