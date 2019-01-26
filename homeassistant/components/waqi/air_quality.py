"""
Air quality platform for the WAQI Component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/air_quality.waqi/
"""
import logging

from homeassistant.components.air_quality import (
    AirQualityEntity, PROP_TO_ATTR)
from homeassistant.components.waqi import SCAN_INTERVAL
from homeassistant.const import ATTR_TIME
from homeassistant.util import Throttle

ATTR_DOMINANT_POLLUANT = 'dominant_polluant'

PROP_TO_ATTR.update({'dominant_polluant': ATTR_DOMINANT_POLLUANT,
                     'update_time': ATTR_TIME})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the requested World Air Quality Index entity."""
    data = discovery_info['data']
    async_add_entities([WaqiQuality(data)], True)


class WaqiQuality(AirQualityEntity):
    """Implementation of a WAQI air quality entity."""

    def __init__(self, data):
        """Initialize the entity."""
        self.waqi_data = data
        self._data = data.data
        self.uid = self.waqi_data.station['uid']
        self.url = self.waqi_data.station['station']['url']
        self.station_name = self.waqi_data.station['station']['name']

    @property
    def attribution(self):
        """Return the attribution."""
        return self.waqi_data.attribution

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self.waqi_data.get('pm25')

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self.waqi_data.get('pm10')

    @property
    def air_quality_index(self):
        """Return the Air Quality Index (AQI)."""
        return self._data.get('aqi')

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        return self.waqi_data.get('o3')

    @property
    def carbon_monoxide(self):
        """Return the CO (carbon monoxide) level."""
        return self.waqi_data.get('co')

    @property
    def sulphur_dioxide(self):
        """Return the SO2 (sulphur dioxide) level."""
        return self.waqi_data.get('so2')

    @property
    def nitrogen_dioxide(self):
        """Return the NO2 (nitrogen dioxide) level."""
        return self.waqi_data.get('no2')

    @property
    def dominant_polluant(self):
        """Return the dominant polluant."""
        return self._data.get('dominentpol')

    @property
    def name(self):
        """Return the name of the entity."""
        if self.station_name:
            return 'WAQI {}'.format(self.station_name)
        return 'WAQI {}'.format(self.url if self.url else self.uid)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:cloud'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'µg/m3'

    @property
    def update_time(self):
        """Return the update time."""
        return self.waqi_data.update_time

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the latest data and updates the states."""
        await self.waqi_data.async_update()
