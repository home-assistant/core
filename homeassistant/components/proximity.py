"""
Support for tracking the proximity of a device.

Component to monitor the proximity of devices to a particular zone and the
direction of travel.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/proximity/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_ZONE, CONF_DEVICES, CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_state_change
from homeassistant.util.distance import convert
from homeassistant.util.location import distance

_LOGGER = logging.getLogger(__name__)

ATTR_DIR_OF_TRAVEL = 'dir_of_travel'
ATTR_DIST_FROM = 'dist_to_zone'
ATTR_NEAREST = 'nearest'

CONF_IGNORED_ZONES = 'ignored_zones'
CONF_TOLERANCE = 'tolerance'

DEFAULT_DIR_OF_TRAVEL = 'not set'
DEFAULT_DIST_TO_ZONE = 'not set'
DEFAULT_NEAREST = 'not set'
DEFAULT_PROXIMITY_ZONE = 'home'
DEFAULT_TOLERANCE = 1
DEPENDENCIES = ['zone', 'device_tracker']
DOMAIN = 'proximity'

UNITS = ['km', 'm', 'mi', 'ft']

ZONE_SCHEMA = vol.Schema({
    vol.Optional(CONF_ZONE, default=DEFAULT_PROXIMITY_ZONE): cv.string,
    vol.Optional(CONF_DEVICES, default=[]):
        vol.All(cv.ensure_list, [cv.entity_id]),
    vol.Optional(CONF_IGNORED_ZONES, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): cv.positive_int,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): vol.All(cv.string, vol.In(UNITS)),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: ZONE_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup_proximity_component(hass, name, config):
    """Set up the individual proximity component."""
    ignored_zones = config.get(CONF_IGNORED_ZONES)
    proximity_devices = config.get(CONF_DEVICES)
    tolerance = config.get(CONF_TOLERANCE)
    proximity_zone = name
    unit_of_measurement = config.get(
        CONF_UNIT_OF_MEASUREMENT, hass.config.units.length_unit)
    zone_id = 'zone.{}'.format(config.get(CONF_ZONE))

    proximity = Proximity(hass, proximity_zone, DEFAULT_DIST_TO_ZONE,
                          DEFAULT_DIR_OF_TRAVEL, DEFAULT_NEAREST,
                          ignored_zones, proximity_devices, tolerance,
                          zone_id, unit_of_measurement)
    proximity.entity_id = '{}.{}'.format(DOMAIN, proximity_zone)

    proximity.schedule_update_ha_state()

    track_state_change(
        hass, proximity_devices, proximity.check_proximity_state_change)

    return True


def setup(hass, config):
    """Get the zones and offsets from configuration.yaml."""
    for zone, proximity_config in config[DOMAIN].items():
        setup_proximity_component(hass, zone, proximity_config)

    return True


class Proximity(Entity):
    """Representation of a Proximity."""

    def __init__(self, hass, zone_friendly_name, dist_to, dir_of_travel,
                 nearest, ignored_zones, proximity_devices, tolerance,
                 proximity_zone, unit_of_measurement):
        """Initialize the proximity."""
        self.hass = hass
        self.friendly_name = zone_friendly_name
        self.dist_to = dist_to
        self.dir_of_travel = dir_of_travel
        self.nearest = nearest
        self.ignored_zones = ignored_zones
        self.proximity_devices = proximity_devices
        self.tolerance = tolerance
        self.proximity_zone = proximity_zone
        self._unit_of_measurement = unit_of_measurement

    @property
    def name(self):
        """Return the name of the entity."""
        return self.friendly_name

    @property
    def state(self):
        """Return the state."""
        return self.dist_to

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DIR_OF_TRAVEL: self.dir_of_travel,
            ATTR_NEAREST: self.nearest,
        }

    def check_proximity_state_change(self, entity, old_state, new_state):
        """Perform the proximity checking."""
        entity_name = new_state.name
        devices_to_calculate = False
        devices_in_zone = ''

        zone_state = self.hass.states.get(self.proximity_zone)
        proximity_latitude = zone_state.attributes.get('latitude')
        proximity_longitude = zone_state.attributes.get('longitude')

        # Check for devices in the monitored zone.
        for device in self.proximity_devices:
            device_state = self.hass.states.get(device)

            if device_state is None:
                devices_to_calculate = True
                continue

            if device_state.state not in self.ignored_zones:
                devices_to_calculate = True

            # Check the location of all devices.
            if (device_state.state).lower() == (self.friendly_name).lower():
                device_friendly = device_state.name
                if devices_in_zone != '':
                    devices_in_zone = devices_in_zone + ', '
                devices_in_zone = devices_in_zone + device_friendly

        # No-one to track so reset the entity.
        if not devices_to_calculate:
            self.dist_to = 'not set'
            self.dir_of_travel = 'not set'
            self.nearest = 'not set'
            self.schedule_update_ha_state()
            return

        # At least one device is in the monitored zone so update the entity.
        if devices_in_zone != '':
            self.dist_to = 0
            self.dir_of_travel = 'arrived'
            self.nearest = devices_in_zone
            self.schedule_update_ha_state()
            return

        # We can't check proximity because latitude and longitude don't exist.
        if 'latitude' not in new_state.attributes:
            return

        # Collect distances to the zone for all devices.
        distances_to_zone = {}
        for device in self.proximity_devices:
            # Ignore devices in an ignored zone.
            device_state = self.hass.states.get(device)
            if device_state.state in self.ignored_zones:
                continue

            # Ignore devices if proximity cannot be calculated.
            if 'latitude' not in device_state.attributes:
                continue

            # Calculate the distance to the proximity zone.
            dist_to_zone = distance(proximity_latitude,
                                    proximity_longitude,
                                    device_state.attributes['latitude'],
                                    device_state.attributes['longitude'])

            # Add the device and distance to a dictionary.
            distances_to_zone[device] = round(
                convert(dist_to_zone, 'm', self.unit_of_measurement), 1)

        # Loop through each of the distances collected and work out the
        # closest.
        closest_device = None  # type: str
        dist_to_zone = None  # type: float

        for device in distances_to_zone:
            if not dist_to_zone or distances_to_zone[device] < dist_to_zone:
                closest_device = device
                dist_to_zone = distances_to_zone[device]

        # If the closest device is one of the other devices.
        if closest_device != entity:
            self.dist_to = round(distances_to_zone[closest_device])
            self.dir_of_travel = 'unknown'
            device_state = self.hass.states.get(closest_device)
            self.nearest = device_state.name
            self.schedule_update_ha_state()
            return

        # Stop if we cannot calculate the direction of travel (i.e. we don't
        # have a previous state and a current LAT and LONG).
        if old_state is None or 'latitude' not in old_state.attributes:
            self.dist_to = round(distances_to_zone[entity])
            self.dir_of_travel = 'unknown'
            self.nearest = entity_name
            self.schedule_update_ha_state()
            return

        # Reset the variables
        distance_travelled = 0

        # Calculate the distance travelled.
        old_distance = distance(proximity_latitude, proximity_longitude,
                                old_state.attributes['latitude'],
                                old_state.attributes['longitude'])
        new_distance = distance(proximity_latitude, proximity_longitude,
                                new_state.attributes['latitude'],
                                new_state.attributes['longitude'])
        distance_travelled = round(new_distance - old_distance, 1)

        # Check for tolerance
        if distance_travelled < self.tolerance * -1:
            direction_of_travel = 'towards'
        elif distance_travelled > self.tolerance:
            direction_of_travel = 'away_from'
        else:
            direction_of_travel = 'stationary'

        # Update the proximity entity
        self.dist_to = round(dist_to_zone)
        self.dir_of_travel = direction_of_travel
        self.nearest = entity_name
        self.schedule_update_ha_state()
        _LOGGER.debug('proximity.%s update entity: distance=%s: direction=%s: '
                      'device=%s', self.friendly_name, round(dist_to_zone),
                      direction_of_travel, entity_name)

        _LOGGER.info('%s: proximity calculation complete', entity_name)
