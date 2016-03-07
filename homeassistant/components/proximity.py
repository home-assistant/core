"""
custom_components.proximity
~~~~~~~~~~~~~~~~~~~~~~~~~

proximity:
  home:
    zone: home
    ignored_zones:
      - twork
      - elschool
    devices:
      - nwaring_nickmobile
      - eleanorsiphone
      - tsiphone
    tolerance: 1
    name: Home
  work:
    type: zone
    zone: work
    ignored_zones:
      - home
    devices:
      - nwaring_nickmobile
    tolerance: 10
    name: Work Nick
  nick:
    type: device
    device: nwaring_nickmobile
    zones:
      - home
      - work
    tolerance: 1
    name: Nick
"""

import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_state_change
from homeassistant.util.location import distance
from homeassistant.components import zone
from homeassistant.const import CONF_NAME

DEPENDENCIES = ['zone', 'device_tracker']

# domain for the component
DOMAIN = 'proximity'

# default tolerance
DEFAULT_TOLERANCE = 1

# default zone
DEFAULT_PROXIMITY_ZONE = 'home'

# default type
DEFAULT_TYPE = 'zone'

# entity attributes
ATTR_DIST_FROM = 'dist_to_zone'
ATTR_DIR_OF_TRAVEL = 'dir_of_travel'
ATTR_NEAREST = 'nearest'
ATTR_FRIENDLY_NAME = 'friendly_name'
ATTR_TYPE = 'proximity_type'

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """ get the zones and offsets from configuration.yaml"""

    proximities = []
    if config.get(DOMAIN) is None:
        return False

    for prox, prox_config in config[DOMAIN].items():

        if not isinstance(prox_config, dict):
            _LOGGER.error("Missing configuration data for proximity %s", prox)
            continue

        proximity_type = None
        friendly_name = None
        tolerance = None
        zone_friendly_name = None
        ignored_zones = None
        proximity_devices = None
        proximity_zone = None
        proximity_device = None
        proximity_zones = None

        proximity_type = prox_config.get('type', DEFAULT_TYPE)

        entity_id = None

        if proximity_type == 'zone':
            # get the devices from configuration.yaml
            if 'devices' not in prox_config:
                _LOGGER.error('devices not found in config')
                continue

            proximity_devices = []
            for variable in prox_config['devices']:
                proximity_devices.append('device_tracker.' + variable)

            ignored_zones = []
            if 'ignored_zones' in prox_config:
                for variable in prox_config['ignored_zones']:
                    ignored_zones.append(variable)

            # get the direction of travel tolerance from configuration.yaml
            tolerance = prox_config.get('tolerance', DEFAULT_TOLERANCE)

            # get the zone to monitor proximity to from configuration.yaml
            proximity_zone = 'zone.' + prox_config.get('zone',
                                                       DEFAULT_PROXIMITY_ZONE)

            friendly_name = prox_config.get(CONF_NAME, prox)

            entity_id = DOMAIN + '.' + prox

            state = hass.states.get(proximity_zone)
            zone_friendly_name = (state.name).lower()

        elif proximity_type == 'device':
            # get the devices from configuration.yaml
            if 'device' not in prox_config:
                _LOGGER.error('device not found in config')
                continue

            proximity_device = 'device_tracker.' + prox_config.get('device')

            # get the direction of travel tolerance from configuration.yaml
            tolerance = prox_config.get('tolerance', DEFAULT_TOLERANCE)

            # get the zone to monitor proximity to from configuration.yaml
            if 'zones' not in prox_config:
                _LOGGER.error('zones not found in config')
                continue
            proximity_zones = []
            for variable in prox_config['zones']:
                proximity_zones.append('zone.' + variable)

            friendly_name = prox_config.get(CONF_NAME, prox)

            entity_id = DOMAIN + '.' + prox

        if entity_id is not None:
            proximity = Proximity(hass,
                                  proximity_type,
                                  friendly_name,
                                  tolerance,
                                  zone_friendly_name,
                                  ignored_zones,
                                  proximity_devices,
                                  proximity_zone,
                                  proximity_device,
                                  proximity_zones)
            proximity.entity_id = entity_id

            proximity.update_ha_state()
            proximity.check_proximity_state_change(None, None, None)

            proximities.append(proximity)
            # main command to monitor proximity of devices
            if proximity_type == 'zone':
                track_state_change(hass, proximity.proximity_devices,
                                   proximity.check_proximity_state_change)
            elif proximity_type == 'device':
                track_state_change(hass, proximity.proximity_device,
                                   proximity.check_proximity_state_change)

    if not proximities:
        _LOGGER.error("No proximities added")
        return False

    # Tells the bootstrapper that the component was successfully initialized
    return True


class Proximity(Entity):  # pylint: disable=too-many-instance-attributes
    """ Represents a Proximity in Home Assistant. """
    def __init__(self, hass, proximity_type, friendly_name, tolerance,
                 zone_friendly_name, ignored_zones, proximity_devices,
                 proximity_zone, proximity_device, proximity_zones):
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.proximity_type = proximity_type
        self.friendly_name = friendly_name
        self.dist_to = 'not set'
        self.dir_of_travel = 'not set'
        self.nearest = 'not set'
        self.tolerance = tolerance

        self.zone_friendly_name = zone_friendly_name
        self.ignored_zones = ignored_zones
        self.proximity_devices = proximity_devices
        self.proximity_zone = proximity_zone

        self.proximity_device = proximity_device
        self.proximity_zones = proximity_zones

    @property
    def state(self):
        if self.proximity_type == 'zone':
            return self.dist_to
        elif self.proximity_type == 'device':
            return self.nearest

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity """
        if self.proximity_type == 'zone':
            return "km"

    @property
    def state_attributes(self):
        if self.proximity_type == 'zone':
            return {
                ATTR_DIR_OF_TRAVEL: self.dir_of_travel,
                ATTR_NEAREST: self.nearest,
                ATTR_FRIENDLY_NAME: self.friendly_name,
                ATTR_TYPE: self.proximity_type
            }
        elif self.proximity_type == 'device':
            return {
                ATTR_DIR_OF_TRAVEL: self.dir_of_travel,
                ATTR_DIST_FROM: self.dist_to,
                ATTR_FRIENDLY_NAME: self.friendly_name,
                ATTR_TYPE: self.proximity_type
            }

    def check_proximity_zone(self, entity, old_state, new_state):
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """ Function to perform the proximity checking for a zone """
        if entity is None:
            for device in self.proximity_devices:
                device_state = self.hass.states.get(device)

                if 'latitude' in device_state.attributes:
                    entity = device
                    new_state = device_state
                    break

        if entity is None:
            return False

        entity_name = new_state.name
        devices_to_calculate = self.ignored_zones == []
        devices_have_coordinates = False
        devices_in_zone = ''

        zone_state = self.hass.states.get(self.proximity_zone)
        proximity_latitude = zone_state.attributes.get('latitude')
        proximity_longitude = zone_state.attributes.get('longitude')

        # check for devices in the monitored zone
        for device in self.proximity_devices:
            device_state = self.hass.states.get(device)

            if 'latitude' not in device_state.attributes:
                continue

            devices_have_coordinates = True

            device_state_lat = device_state.attributes['latitude']
            device_state_lon = device_state.attributes['longitude']

            for ignored_zone in self.ignored_zones:
                ignored_zone_state = self.hass.states.get('zone.' +
                                                          ignored_zone)
                if not zone.in_zone(ignored_zone_state,
                                    device_state_lat,
                                    device_state_lon):
                    devices_to_calculate = True

            # check the location of all devices
            if zone.in_zone(zone_state,
                            device_state_lat,
                            device_state_lon):
                device_friendly = device_state.name
                if devices_in_zone != '':
                    devices_in_zone = devices_in_zone + ', '
                devices_in_zone = devices_in_zone + device_friendly

        # at least one device is in the monitored zone so update the entity
        if devices_in_zone != '':
            self.dist_to = 0
            self.dir_of_travel = 'arrived'
            self.nearest = devices_in_zone
            self.update_ha_state()
            return

        # no-one to track so reset the entity
        if not devices_to_calculate or not devices_have_coordinates:
            self.dist_to = 'not set'
            self.dir_of_travel = 'not set'
            self.nearest = 'not set'
            self.update_ha_state()
            return

        # we can't check proximity because latitude and longitude don't exist
        if 'latitude' not in new_state.attributes:
            return

        # collect distances to the zone for all devices
        distances_to_zone = {}
        for device in self.proximity_devices:
            # ignore devices in an ignored zone
            device_state = self.hass.states.get(device)

            # ignore devices if proximity cannot be calculated
            if 'latitude' not in device_state.attributes:
                continue

            device_state_lat = device_state.attributes['latitude']
            device_state_lon = device_state.attributes['longitude']

            device_in_ignored_zone = False
            for ignored_zone in self.ignored_zones:
                ignored_zone_state = self.hass.states.get('zone.' +
                                                          ignored_zone)
                if zone.in_zone(ignored_zone_state,
                                device_state_lat,
                                device_state_lon):
                    device_in_ignored_zone = True
                    continue
            if device_in_ignored_zone:
                continue

            # calculate the distance to the proximity zone
            dist_to_zone = distance(proximity_latitude,
                                    proximity_longitude,
                                    device_state_lat,
                                    device_state_lon)

            # add the device and distance to a dictionary
            distances_to_zone[device] = round(dist_to_zone / 1000, 1)

        # loop through each of the distances collected and work out the closest
        closest_device = ''
        dist_to_zone = 1000000

        for device in distances_to_zone:
            if distances_to_zone[device] < dist_to_zone:
                closest_device = device
                dist_to_zone = distances_to_zone[device]

        # if the closest device is one of the other devices
        if closest_device != entity:
            self.dist_to = round(distances_to_zone[closest_device])
            self.dir_of_travel = 'unknown'
            device_state = self.hass.states.get(closest_device)
            self.nearest = device_state.name
            self.update_ha_state()
            return

        # stop if we cannot calculate the direction of travel (i.e. we don't
        # have a previous state and a current LAT and LONG)
        if old_state is None or 'latitude' not in old_state.attributes:
            self.dist_to = round(distances_to_zone[entity])
            self.dir_of_travel = 'unknown'
            self.nearest = entity_name
            self.update_ha_state()
            return

        # reset the variables
        distance_travelled = 0

        # calculate the distance travelled
        old_distance = distance(proximity_latitude, proximity_longitude,
                                old_state.attributes['latitude'],
                                old_state.attributes['longitude'])
        new_distance = distance(proximity_latitude, proximity_longitude,
                                new_state.attributes['latitude'],
                                new_state.attributes['longitude'])
        distance_travelled = round(new_distance - old_distance, 1)

        # check for tolerance
        if distance_travelled < self.tolerance * -1:
            direction_of_travel = 'towards'
        elif distance_travelled > self.tolerance:
            direction_of_travel = 'away_from'
        else:
            direction_of_travel = 'stationary'

        # update the proximity entity
        self.dist_to = round(dist_to_zone)
        self.dir_of_travel = direction_of_travel
        self.nearest = entity_name
        self.update_ha_state()
        _LOGGER.debug('proximity.%s update entity: distance=%s: direction=%s: '
                      'device=%s', self.friendly_name, round(dist_to_zone),
                      direction_of_travel, entity_name)

        _LOGGER.info('%s: proximity calculation complete', entity_name)

    def check_proximity_device(self, entity, old_state, new_state):
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """ Function to perform the proximity checking  for a device """
        if entity is None:
            device_state = self.hass.states.get(self.proximity_device)

            if 'latitude' in device_state.attributes:
                entity = self.proximity_device
                new_state = device_state

        if entity is None:
            return False

        entity_name = new_state.name

        # we can't check proximity because latitude and longitude don't exist
        if 'latitude' not in new_state.attributes:
            return

        proximity_latitude = new_state.attributes['latitude']
        proximity_longitude = new_state.attributes['longitude']

        # collect distances to the zone for all devices
        distances_to_device = {}
        for proximity_zone in self.proximity_zones:
            zone_state = self.hass.states.get(proximity_zone)

            zone_state_lat = zone_state.attributes['latitude']
            zone_state_lon = zone_state.attributes['longitude']

            if zone.in_zone(zone_state,
                            proximity_latitude,
                            proximity_longitude):
                self.dist_to = 0
                self.dir_of_travel = 'arrived'
                self.nearest = zone_state.name
                self.update_ha_state()
                return

            # calculate the distance to the proximity zone
            dist_to_device = distance(proximity_latitude,
                                      proximity_longitude,
                                      zone_state_lat,
                                      zone_state_lon)

            # add the device and distance to a dictionary
            distances_to_device[proximity_zone] = round(dist_to_device / 1000,
                                                        1)

        # loop through each of the distances collected and work out the closest
        closest_zone = None
        dist_to_device = 0

        for proximity_zone in distances_to_device:
            if (closest_zone is None or
                    distances_to_device[proximity_zone] < dist_to_device):
                closest_zone = proximity_zone
                dist_to_device = distances_to_device[proximity_zone]

        zone_state = self.hass.states.get(closest_zone)
        closest_zone_name = zone_state.name

        if (closest_zone_name != self.nearest or old_state is None or
                'latitude' not in old_state.attributes):
            self.dist_to = round(distances_to_device[closest_zone])
            self.dir_of_travel = 'unknown'
            zone_state = self.hass.states.get(closest_zone)
            self.nearest = zone_state.name
            self.update_ha_state()
            return

        # reset the variables
        distance_travelled = 0

        zone_state = self.hass.states.get(closest_zone)
        zone_state_lat = zone_state.attributes['latitude']
        zone_state_lon = zone_state.attributes['longitude']

        # calculate the distance travelled
        old_distance = distance(zone_state_lat, zone_state_lon,
                                old_state.attributes['latitude'],
                                old_state.attributes['longitude'])
        new_distance = distance(zone_state_lat, zone_state_lon,
                                new_state.attributes['latitude'],
                                new_state.attributes['longitude'])
        distance_travelled = round(new_distance - old_distance, 1)

        # check for tolerance
        if distance_travelled < self.tolerance * -1:
            direction_of_travel = 'towards'
        elif distance_travelled > self.tolerance:
            direction_of_travel = 'away_from'
        else:
            direction_of_travel = 'stationary'

        # update the proximity entity
        self.dist_to = round(new_distance)
        self.dir_of_travel = direction_of_travel
        self.nearest = zone_state.name
        self.update_ha_state()
        _LOGGER.debug('proximity.%s update entity: distance=%s: direction=%s: '
                      'device=%s', self.friendly_name, round(new_distance),
                      direction_of_travel, entity_name)

        _LOGGER.info('%s: proximity calculation complete', entity_name)

    def check_proximity_state_change(self, entity, old_state, new_state):
        """ Function to perform the proximity checking  for a device """
        if self.proximity_type == 'zone':
            self.check_proximity_zone(entity, old_state, new_state)
        elif self.proximity_type == 'device':
            self.check_proximity_device(entity, old_state, new_state)
