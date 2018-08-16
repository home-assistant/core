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

from homeassistant.components import group
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant import util

_LOGGER = logging.getLogger(__name__)

DEFAULT_SORT_GROUP_ENTRIES_REVERSE = False
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


class GeoLocationDeviceManager:
    """Device manager for geo location events."""

    def __init__(self, hass, add_devices, name, sort_group_entries_reverse):
        """Initialize the geo location device manager."""
        self._hass = hass
        self._add_devices = add_devices
        self._name = name
        self._sort_group_entries_reverse = sort_group_entries_reverse
        self._managed_devices = []
        self.group = group.Group.create_group(self._hass, name,
                                              object_id=util.slugify(name))

    @property
    def name(self):
        """Return the name."""
        return self._name

    def _generate_entity_id(self, event_name):
        """Generate device entity id from the manager name and event name."""
        entity_ids = [device.entity_id for device in self._managed_devices]
        entity_id = generate_entity_id(ENTITY_ID_FORMAT,
                                       '{} {}'.format(self.name, event_name),
                                       entity_ids, hass=self._hass)
        return entity_id

    def _group_devices(self):
        """Re-group all entities."""
        # Sort entries in group by their state attribute (ascending).
        devices = sorted(self._managed_devices.copy(),
                         key=lambda device: device.state,
                         reverse=self._sort_group_entries_reverse)
        entity_ids = [device.entity_id for device in devices]
        # Update group.
        self.group.update_tracked_entity_ids(entity_ids)


class GeoLocationEvent(Entity):
    """This represents an external event with an associated geo location."""

    def __init__(self, hass, entity_id, name, distance, latitude, longitude,
                 unit_of_measurement, icon):
        """Initialize entity with data provided."""
        self.hass = hass
        self.entity_id = entity_id
        self._name = name
        self._distance = distance
        self._latitude = latitude
        self._longitude = longitude
        self._unit_of_measurement = unit_of_measurement
        self._icon = icon

    @property
    def should_poll(self):
        """No polling needed for a generic geo location event."""
        return False

    @property
    def name(self) -> Optional[str]:
        """Return the name of the event."""
        return self._name

    @name.setter
    def name(self, value):
        """Set event's name."""
        self._name = value

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
