"""
custom_components.proximity_zones
~~~~~~~~~~~~~~~~~~~~~~~~~

proximity_zones:
- zone: home
    ignored_zones:
      - twork
      - elschool
    devices:
      - device_tracker.nwaring_nickmobile
      - device_tracker.eleanorsiphone
      - device_tracker.tsiphone
    tolerance: 1
- zone: work
    ignored_zones:
      - home
    devices:
      - device_tracker.nwaring_nickmobile
    tolerance: 10
"""

import logging
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.entity import Entity
from homeassistant.util.location import distance
from homeassistant.components import zone
from homeassistant.const import CONF_NAME

DEPENDENCIES = ['zone', 'device_tracker']

# domain for the component
DOMAIN = 'proximity_zones'

# default tolerance
DEFAULT_TOLERANCE = 1

# default zone
DEFAULT_PROXIMITY_ZONE = 'home'

# entity attributes
ATTR_DIST_FROM = 'dist_to_zone'
ATTR_DIR_OF_TRAVEL = 'dir_of_travel'
ATTR_NEAREST = 'nearest'
ATTR_FRIENDLY_NAME = 'friendly_name'

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):  # pylint: disable=too-many-locals,too-many-statements
    """ get the zones and offsets from configuration.yaml"""

    proximities = []
    if config.get(DOMAIN) is None:
        return False

    for prox, prox_config in config[DOMAIN].items():

        if not isinstance(prox_config, dict):
            _LOGGER.error("Missing configuration data for proximity %s", prox)
            continue

        # get the devices from configuration.yaml
        if 'devices' not in prox_config:
            _LOGGER.error('devices not found in config')
            continue

        proximity_devices = []
        for variable in prox_config['devices']:
            proximity_devices.append(variable)

        ignored_zones = []
        if 'ignored_zones' in prox_config:
            for variable in prox_config['ignored_zones']:
                ignored_zones.append(variable)

        # get the direction of travel tolerance from configuration.yaml
        tolerance = prox_config.get('tolerance', DEFAULT_TOLERANCE)

        # get the zone to monitor proximity to from configuration.yaml
        proximity_zone = prox_config.get('zone', DEFAULT_PROXIMITY_ZONE)

        friendly_name = prox_config.get(CONF_NAME, prox)

        entity_id = DOMAIN + '.' + prox
        proximity_zone = 'zone.' + proximity_zone

        state = hass.states.get(proximity_zone)
        zone_friendly_name = (state.name).lower()

        # set the default values
        dist_to_zone = 'not set'
        dir_of_travel = 'not set'
        nearest = 'not set'

        proximity = Proximity(hass, zone_friendly_name, dist_to_zone,
                              dir_of_travel, nearest, ignored_zones,
                              proximity_devices, tolerance, proximity_zone,
                              friendly_name)
        proximity.entity_id = entity_id

        proximity.update_ha_state()
        proximity.check_proximity_initial_state()

        proximities.append(proximity)
        # main command to monitor proximity of devices
        track_state_change(hass, proximity.proximity_devices,
                           proximity.check_proximity_state_change)

    if not proximities:
        _LOGGER.error("No proximities added")
        return False

    # Tells the bootstrapper that the component was successfully initialized
    return True


class Proximity(Entity):  # pylint: disable=too-many-instance-attributes
    """ Represents a Proximity in Home Assistant. """
    def __init__(self, hass, zone_friendly_name, dist_to, dir_of_travel,
                 nearest, ignored_zones, proximity_devices, tolerance,
                 proximity_zone, friendly_name):
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.friendly_name = friendly_name
        self.zone_friendly_name = zone_friendly_name
        self.dist_to = dist_to
        self.dir_of_travel = dir_of_travel
        self.nearest = nearest
        self.ignored_zones = ignored_zones
        self.proximity_devices = proximity_devices
        self.tolerance = tolerance
        self.proximity_zone = proximity_zone

    @property
    def state(self):
        return self.dist_to

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity """
        return "km"

    @property
    def state_attributes(self):
        return {
            ATTR_DIR_OF_TRAVEL: self.dir_of_travel,
            ATTR_NEAREST: self.nearest,
            ATTR_FRIENDLY_NAME: self.friendly_name
        }

    def check_proximity_state_change(self, entity, old_state, new_state):
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """ Function to perform the proximity checking """
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

    def check_proximity_initial_state(self):
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """ Function to perform the proximity checking in the initial state """
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

        self.dist_to = round(distances_to_zone[closest_device])
        self.dir_of_travel = 'unknown'
        device_state = self.hass.states.get(closest_device)
        self.nearest = device_state.name
        self.update_ha_state()
