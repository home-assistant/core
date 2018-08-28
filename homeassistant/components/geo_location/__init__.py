"""
Geo Location component.

This component covers platforms that deal with external events that contain
a geo location related to the installed HA instance.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/geo_location/
"""
import logging
from datetime import timedelta
from typing import Optional

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE = 'distance'
DOMAIN = 'geo_location'
ENTITY_ID_FORMAT = DOMAIN + '.{}'
GROUP_NAME_ALL_EVENTS = 'All Geo Location Events'
SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass, config):
    """Set up this component."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_EVENTS)
    await component.async_setup(config)
    return True


class GeoLocationEvent(Entity):
    """This represents an external event with an associated geo location."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.distance is not None:
            return round(self.distance, 1)
        return None

    @property
    def distance(self) -> Optional[float]:
        """Return distance value of this external event."""
        return None

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of this external event."""
        return None

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of this external event."""
        return None

    @property
    def state_attributes(self):
        """Return the state attributes of this external event."""
        data = {}
        if self.latitude is not None:
            data[ATTR_LATITUDE] = round(self.latitude, 5)
        if self.longitude is not None:
            data[ATTR_LONGITUDE] = round(self.longitude, 5)
        return data
