"""
Geo Location component.

This component covers platforms that deal with external events that contain
a geo location related to the installed HA instance.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/geo_location/
"""
import logging
from datetime import timedelta

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'geo_location'
ENTITY_ID_FORMAT = DOMAIN + '.{}'
GROUP_NAME_ALL_EVENTS = 'All Geo Location Events'
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass, config):
    """Setup this component."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_EVENTS)
    await component.async_setup(config)
    return True


class GeoLocationEvent(Entity):
    """This represents an external event with an associated geo location."""

    def __init__(self, hass, entity_id, distance, latitude, longitude,
                 unit_of_measurement, icon):
        """Initialize entity with data provided."""
        self.hass = hass
        self.entity_id = entity_id
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._unit_of_measurement = unit_of_measurement
        self._icon = icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self._distance, 1)

    @property
    def distance(self):
        """Return distance value of this external event."""
        return self._distance

    @distance.setter
    def distance(self, value):
        """Set event's distance."""
        self._distance = value

    @property
    def latitude(self):
        """Return latitude value of this external event."""
        return self._latitude

    @latitude.setter
    def latitude(self, value):
        """Set event's latitude."""
        self._latitude = value

    @property
    def longitude(self):
        """Return longitude value of this external event."""
        return self._longitude

    @longitude.setter
    def longitude(self, value):
        """Set event's longitude."""
        self._longitude = value

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_LATITUDE: self._latitude, ATTR_LONGITUDE: self._longitude}
