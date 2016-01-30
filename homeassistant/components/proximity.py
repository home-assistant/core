"""
custom_components.proximity
~~~~~~~~~~~~~~~~~~~~~~~~~
Component to monitor the proximity of devices to a particular zone and the
direction of travel. The result is an entity created in HA which maintains
the proximity data

This component is useful to reduce the number of automation rules required
when wanting to perform automations based on locations outside a particular
zone. The standard HA zone and state based triggers allow similar control
but the number of rules grows exponentially when factors such as direction
of travel need to be taken into account. Some examples of its use include:
- Increase thermostat temperature as you near home
- Decrease temperature the further away from home you travel

Use configuration.yaml to enable the user to easily tune a number of settings:
- Zone: the zone to which this component is measuring the distance to. Default
  is the home zone
- Ignored Zones: where proximity is not calculated (e.g. work or school)
- Devices: a list of devices to compare location against to check closeness to
  the configured zone
- Tolerance: the tolerance used to calculate the direction of travel in metres
  (to filter out small GPS co-ordinate changes

Loging levels debug, info and error are in use

Example configuration.yaml entry:
proximity:
  zone: home
  ignored_zones:
    - twork
    - elschool
  devices:
    - device_tracker.nwaring_nickmobile
    - device_tracker.eleanorsiphone
    - device_tracker.tsiphone
  tolerance: 50
"""

import logging
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.entity import Entity
from homeassistant.util.location import distance
from homeassistant.const import (ATTR_HIDDEN)

DEPENDENCIES = ['zone', 'device_tracker']

# domain for the component
DOMAIN = 'proximity'

# default tolerance
DEFAULT_TOLERANCE = 1

# default zone
DEFAULT_PROXIMITY_ZONE = 'home'

# entity attributes
ATTR_DIST_FROM = 'dist_from_zone'
ATTR_DIR_OF_TRAVEL = 'dir_of_travel'
ATTR_NEAREST_DEVICE = 'nearest_device'

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config): # pylint: disable=too-many-locals,too-many-statements
    """ get the zones and offsets from configuration.yaml"""
    ignored_zones = []
    if 'ignored_zones' in config[DOMAIN]:
        for variable in config[DOMAIN]['ignored_zones']:
            ignored_zones.append(variable)
            _LOGGER.info('Ignored zones loaded: %s', variable)

    # get the devices from configuration.yaml
    if 'devices' not in config[DOMAIN]:
        _LOGGER.error('devices not found in config')
        return False
    else:
        proximity_devices = []
        for variable in config[DOMAIN]['devices']:
            proximity_devices.append(variable)
            _LOGGER.info('Proximity device added: %s', variable)

    # get the direction of travel tolerance from configuration.yaml
    if 'tolerance' in config[DOMAIN]:
        tolerance = config[DOMAIN]['tolerance']
    else:
        tolerance = DEFAULT_TOLERANCE
    _LOGGER.debug('tolerance set to: %s', tolerance)

    # get the zone to monitor proximity to from configuration.yaml
    if 'zone' in config[DOMAIN]:
        proximity_zone = config[DOMAIN]['zone']
    else:
        proximity_zone = DEFAULT_PROXIMITY_ZONE
    _LOGGER.info('Zone set to %s', proximity_zone)

    entity_id = DOMAIN + '.' + proximity_zone
    proximity_zone = 'zone.' + proximity_zone

    state = hass.states.get(proximity_zone)
    proximity_latitude = state.attributes.get('latitude')
    proximity_longitude = state.attributes.get('longitude')
    _LOGGER.debug('Zone settings: LAT:%s LONG:%s', proximity_latitude,
                  proximity_longitude)

    # create an entity so that the proximity values can be used for other
    # components
    entities = set()

    # set the default values
    dist_from_zone = 'not set'
    dir_of_travel = 'not set'
    nearest_device = 'not set'

    proximity = Proximity(hass, dist_from_zone, dir_of_travel, nearest_device)
    proximity.entity_id = entity_id

    proximity.update_ha_state()
    entities.add(proximity.entity_id)

    def check_proximity_state_change(entity, old_state, new_state):
        # pylint: disable=too-many-branches,too-many-statements
        """ Function to perform the proximity checking """
        entity_name = new_state.attributes['friendly_name']
        device_is_in_zone = False

        # check for devices in the monitored zone
        for device in proximity_devices:
            device_state = hass.states.get(device)
            if device_state.state == config[DOMAIN]['zone']:
                device_is_in_zone = True
                _LOGGER.info('%s Device: %s is in the monitored zone: %s',
                             entity_name, device, device_state.state)

        if device_is_in_zone:
            entity_state = hass.states.get(entity_id)
            if not entity_state.attributes[ATTR_DIR_OF_TRAVEL] == 'arrived':
                proximity.dist_from = 0
                proximity.dir_of_travel = 'arrived'
                proximity.nearest_device = entity_name
                proximity.update_ha_state()
                _LOGGER.debug('%s Update entity: distance = 0: direction = '
                              'arrived: device = %s', entity_id, entity_name)
            else:
                _LOGGER.debug('%s Entity not updted: %s is in proximity '
                              'zone:%s', entity_id, entity_name,
                              config[DOMAIN]['zone'])
            return

        # check that the device is not in an ignored zone
        if new_state.state in ignored_zones:
            _LOGGER.info('%s Device is in an ignored zone: %s', entity_id,
                         entity_name)
            return

        # check for latitude and longitude (on startup these values may not
        # exist)
        if 'latitude' not in new_state.attributes:
            _LOGGER.info('%s: not LAT or LONG current position cannot be '
                         'calculated', entity_name)
            return

        # calculate the distance of the device from the monitored zone
        distance_from_zone = distance(proximity_latitude,
                                      proximity_longitude,
                                      new_state.attributes['latitude'],
                                      new_state.attributes['longitude'])
        distance_from_zone = round(distance_from_zone / 1000, 1)
        _LOGGER.info('%s: distance from zone is: %s km', entity_name,
                     distance_from_zone)

        # compare distance with other devices
        # default behaviour
        device_is_closest_to_zone = True

        for device in proximity_devices:
            # ignore the device we're working on
            if device == entity:
                continue

            # ignore the device if it's in an ingore zone
            device_state = hass.states.get(device)
            if device_state in ignored_zones:
                _LOGGER.debug('%s: no need to compare with %s - device is in '
                              'ignored zone', entity_name, device)
                continue

            # ignore the device if proximity cannot be calculated
            if 'latitude' not in device_state.attributes:
                _LOGGER.debug('%s: cannot compare with %s - no location '
                              'attributes', entity_name, device)
                continue

            # calculate the distance from the proximity zone for the compare
            # device
            compare_dev_dist = distance(proximity_latitude,
                                        proximity_longitude,
                                        device_state.attributes['latitude'],
                                        device_state.attributes['longitude'])
            compare_dev_dist = round(compare_dev_dist / 1000, 1)
            _LOGGER.debug('%s: compare device %s: co-ordintes: LAT %s: LONG: '
                          '%s', entity_name, device,
                          device_state.attributes['latitude'],
                          device_state.attributes['longitude'])

            # stop if a device is found that is closer to home
            if distance_from_zone >= compare_dev_dist:
                device_is_closest_to_zone = False
                _LOGGER.debug('%s: further away than %s: %s compared with %s',
                              entity_name, device, distance_from_zone,
                              compare_dev_dist)
                break

        # if the device is not the closest to the proximity zone
        if not device_is_closest_to_zone:
            _LOGGER.info('%s: device is not closest to zone', entity_name)
            return

        # stop if we cannot calculate the direction of travel (i.e. we don't
        # have a previous state and a current LAT and LONG)
        if old_state is None or 'latitude' not in old_state.attributes:
            proximity.dist_from = round(distance_from_zone)
            proximity.dir_of_travel = 'unknown'
            proximity.nearest_device = entity_name
            proximity.update_ha_state()
            _LOGGER.debug('%s Update entity: distance = %s: direction = '
                          'unknown: device = %s', entity_id,
                          distance_from_zone, entity_name)
            _LOGGER.info('%s: Cannot determine direction of travel as old '
                         'and/or new LAT or LONG are missing', entity_name)
            return

        # reset the variables
        distance_travelled = 0

        old_distance = distance(proximity_latitude, proximity_longitude,
                                old_state.attributes['latitude'],
                                old_state.attributes['longitude'])
        _LOGGER.debug('%s: old distance: %s', entity_name, old_distance)

        new_distance = distance(proximity_latitude, proximity_longitude,
                                new_state.attributes['latitude'],
                                new_state.attributes['longitude'])
        _LOGGER.debug('%s: new distance: %s', entity_name, new_distance)

        distance_travelled = round(new_distance - old_distance, 1)

        # check for tolerance
        if distance_travelled <= tolerance * -1:
            direction_of_travel = 'towards'
            _LOGGER.info('%s: device travelled %s metres: moving %s',
                         entity_name, distance_travelled, direction_of_travel)
        elif distance_travelled > tolerance:
            direction_of_travel = 'away_from'
            _LOGGER.info('%s: device travelled %s metres: moving %s',
                         entity_name, distance_travelled, direction_of_travel)
        else:
            direction_of_travel = 'unknown'
            _LOGGER.info('%s: Cannot determine direction: %s is too small',
                         entity_name, distance_travelled)

        # update the proximity entity
        proximity.dist_from = round(distance_from_zone)
        proximity.dir_of_travel = direction_of_travel
        proximity.nearest_device = entity_name
        proximity.update_ha_state()
        _LOGGER.debug('%s Update entity: distance = %s: direction = %s: '
                      'device = %s', entity_id, round(distance_from_zone),
                      direction_of_travel, entity_name)

        _LOGGER.info('%s: Proximity calculation complete', entity_name)

    # main command to monitor proximity of devices
    track_state_change(hass, proximity_devices,
                       check_proximity_state_change)

    # Tells the bootstrapper that the component was successfully initialized
    return True


class Proximity(Entity):
    """ Represents a Proximity in Home Assistant. """
    def __init__(self, hass, dist_from_zone, dir_of_travel, nearest_device):
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.dist_from = dist_from_zone
        self.dir_of_travel = dir_of_travel
        self.nearest_device = nearest_device

    def should_poll(self):
        return False

    @property
    def state(self):
        return self.dist_from

    @property
    def state_attributes(self):
        return {
            ATTR_DIST_FROM: self.dist_from,
            ATTR_DIR_OF_TRAVEL: self.dir_of_travel,
            ATTR_NEAREST_DEVICE: self.nearest_device,
            ATTR_HIDDEN: True,
        }

    @property
    def direction_of_travel(self):
        """ returns the direction of travel """
        return self.dir_of_travel

    @property
    def distance_from_zone(self):
        """ returns the distance of the closest device to the zone """
        return self.dist_from

    @property
    def nearest_device(self):
        """ returns the name of the device closest to the zone """
        return self.nearest_device
