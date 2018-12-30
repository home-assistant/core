# coding=utf-8
"""
Sensor for checking the air quality around Norway.

Data delivered by luftkvalitet.info and nilu.no.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nilu_air_quality/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.air_pollutants import AirPollutantsEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_SHOW_ON_MAP)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

REQUIREMENTS = ['niluclient==0.1.2']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)

ICON = 'mdi:cloud-outline'

CONF_AREA = 'area'
CONF_STATION = 'stations'
DEFAULT_NAME = 'NILU'

CONF_ATTRIBUTION = "Data provided by luftkvalitet.info and nilu.no"

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
                  'Please only configure station or area.'): cv.ensure_list,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SHOW_ON_MAP, default=False): cv.boolean,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the NILU air quality sensors."""
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
        sensors.append(NiluSensor(client, name, show_on_map))

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


class NiluSensor(AirPollutantsEntity):
    """Single nilu station air sensor."""

    def __init__(self,
                 api_data: NiluData,
                 name: str,
                 show_on_map: bool):
        """Initialize the sensor."""
        self._api = api_data
        self._name = "{} {}".format(name, api_data.data.name)
        self._max_aqi = None
        self._state = None
        self._attrs = {}

        if show_on_map:
            self._attrs[CONF_LATITUDE] = api_data.data.latitude
            self._attrs[CONF_LONGITUDE] = api_data.data.longitude

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return CONF_ATTRIBUTION

    @property
    def device_state_attributes(self) -> dict:
        """Return other details about the sensor state."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return ICON

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        import niluclient as nilu
        if self.air_quality_index \
                and self.air_quality_index < len(nilu.POLLUTION_INDEX):
            return nilu.POLLUTION_INDEX[self.air_quality_index]

        return None

    @property
    def air_quality_index(self) -> str:
        """Return the Air Quality Index (AQI)."""
        return self._max_aqi

    @property
    def carbon_monoxide(self) -> str:
        """Return the CO (carbon monoxide) level."""
        from niluclient import CO
        if CO in self._api.data.sensors:
            sensor = self._api.data.sensors[CO]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def carbon_dioxide(self) -> str:
        """Return the CO2 (carbon dioxide) level."""
        from niluclient import CO2
        if CO2 in self._api.data.sensors:
            sensor = self._api.data.sensors[CO2]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def nitrogen_oxide(self) -> str:
        """Return the N2O (nitrogen oxide) level."""
        from niluclient import NOX
        if NOX in self._api.data.sensors:
            sensor = self._api.data.sensors[NOX]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def nitrogen_monoxide(self) -> str:
        """Return the NO (nitrogen monoxide) level."""
        from niluclient import NO
        if NO in self._api.data.sensors:
            sensor = self._api.data.sensors[NO]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def nitrogen_dioxide(self) -> str:
        """Return the NO2 (nitrogen dioxide) level."""
        from niluclient import NO2
        if NO2 in self._api.data.sensors:
            sensor = self._api.data.sensors[NO2]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def ozone(self) -> str:
        """Return the O3 (ozone) level."""
        from niluclient import OZONE
        if OZONE in self._api.data.sensors:
            sensor = self._api.data.sensors[OZONE]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def particulate_matter_2_5(self) -> str:
        """Return the particulate matter 2.5 level."""
        from niluclient import PM25
        if PM25 in self._api.data.sensors:
            sensor = self._api.data.sensors[PM25]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def particulate_matter_10(self) -> str:
        """Return the particulate matter 10 level."""
        from niluclient import PM10
        if PM10 in self._api.data.sensors:
            sensor = self._api.data.sensors[PM10]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def particulate_matter_0_1(self) -> str:
        """Return the particulate matter 0.1 level."""
        from niluclient import PM1
        if PM1 in self._api.data.sensors:
            sensor = self._api.data.sensors[PM1]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    @property
    def sulphur_dioxide(self) -> str:
        """Return the SO2 (sulphur dioxide) level."""
        from niluclient import SO2
        if SO2 in self._api.data.sensors:
            sensor = self._api.data.sensors[SO2]
            return "{0:.2f} {1}".format(sensor.value,
                                        sensor.unit_of_measurement)

        return None

    def update(self) -> None:
        """Update the sensor."""
        self._api.update()

        sensors = self._api.data.sensors.values()
        if sensors:
            max_index = max([s.pollution_index for s in sensors])
            self._max_aqi = max_index

        self._attrs[ATTR_AREA] = self._api.data.area
