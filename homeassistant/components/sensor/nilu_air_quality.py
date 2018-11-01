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
from homeassistant.const import ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['niluclient==0.1.0']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=30)

CONF_AREAS = 'areas'

AREAS = [
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

POLLUTION_INDEX = [
    "No data",
    'Low',
    'Moderate',
    'High',
    "Extremely high"
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Inclusive(CONF_LATITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.latitude,
    vol.Inclusive(CONF_LONGITUDE, 'coordinates',
                  'Latitude and longitude must exist together'): cv.longitude,
    vol.Optional(CONF_AREAS):
        vol.All(cv.ensure_list, [vol.In(AREAS)]),
})


async def async_setup_platform(hass, config, add_entities,
                               discovery_info=None):
    """Set up the NILU air quality sensors."""
    import niluclient as nilu
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    areas = config.get(CONF_AREAS)

    location_client = nilu.create_location_client(latitude, longitude)

    sensors = []
    for key in location_client.station_names:
        sensors.append(NiluSensor(nilu.create_station_client(key)))

    if areas:
        for area in areas:
            stations = nilu.lookup_stations_in_area(area)
            for station in stations:
                sensors.append(NiluSensor(nilu.create_station_client(station)))

    add_entities(sensors, True)


class NiluSensor(Entity):
    """Single nilu station air sensor."""

    ICON = 'mdi:cloud-outline'

    def __init__(self, api_data):
        """Initialize the sensor."""
        self._api_data = api_data
        self._name = "NILU " + api_data.data.area + " " + api_data.data.name
        self._site_data = None
        self._state = None
        self._updated = None
        self._attrs = {
            ATTR_ATTRIBUTION: "Data provided by luftkvalitet.info and nilu.no"
        }
        self.update()

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
        return self.ICON

    @property
    def device_state_attributes(self) -> dict:
        """Return other details about the sensor state."""
        return self._attrs

    def update(self) -> None:
        """Update the sensor."""
        self._api_data.update()
        self._attrs['updated'] = dt_util.now()

        sensors = self._api_data.data.sensors.values()

        max_index = max([s.pollution_index for s in sensors])
        self._state = POLLUTION_INDEX[max_index]

        self._attrs['max_pollution_index'] = max_index

        for sensor in sensors:
            attr_name = sensor.component
            self._attrs[attr_name + "_value"] = sensor.value
            self._attrs[attr_name + "_unit_of_measurement"] = \
                sensor.unit_of_measurement
            self._attrs[attr_name + "_pollution_index"] = \
                sensor.pollution_index
