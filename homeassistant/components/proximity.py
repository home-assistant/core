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

The Proximity entity which is created has the following values:
state = distance from the monitored zone (in km)
dir_of_travel = direction of the closest device to the monitoed zone. Values
                are:
                'not set'
                'arrived'
                'towards'
                'away_from'
                'unknown'
                'stationary'
dist_to_zone = distance from the monitored zone (in km)

Use configuration.yaml to enable the user to easily tune a number of settings:
- Zone: the zone to which this component is measuring the distance to. Default
  is the home zone
- Ignored Zones: where proximity is not calculated for a device (either the
  device being monitored or ones being compared (e.g. work or school)
- Devices: a list of devices to compare location against to check closeness to
  the configured zone
- Tolerance: the tolerance used to calculate the direction of travel in metres
  (to filter out small GPS co-ordinate changes

Logging levels debug, info and error are in use

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

DEPENDENCIES = ['zone', 'device_tracker']

# domain for the component
DOMAIN = 'proximity'

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
    ignored_zones = []
    if 'ignored_zones' in config[DOMAIN]:
        for variable in config[DOMAIN]['ignored_zones']:
            ignored_zones.append(variable)
            _LOGGER.info('ignored zones loaded: %s', variable)

    # get the devices from configuration.yaml
    if 'devices' not in config[DOMAIN]:
        _LOGGER.error('devices not found in config')
        return False
    else:
        proximity_devices = []
        for variable in config[DOMAIN]['devices']:
            proximity_devices.append(variable)
            _LOGGER.info('proximity device added: %s', variable)

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
    _LOGGER.info('zone set to %s', proximity_zone)

    entity_id = DOMAIN + '.' + proximity_zone
    proximity_zone = 'zone.' + proximity_zone

    state = hass.states.get(proximity_zone)
    proximity_latitude = state.attributes.get('latitude')
    proximity_longitude = state.attributes.get('longitude')
    zone_friendly_name = state.attributes.get('friendly_name')

    _LOGGER.debug('zone settings: LAT:%s LONG:%s', proximity_latitude,
                  proximity_longitude)

    # create an entity so that the proximity values can be used for other
    # components
    entities = set()

    # set the default values
    dist_to_zone = 'not set'
    dir_of_travel = 'not set'
    nearest = 'not set'

    proximity = Proximity(hass, zone_friendly_name, dist_to_zone,
                          dir_of_travel, nearest)
    proximity.entity_id = entity_id

    proximity.update_ha_state()
    entities.add(proximity.entity_id)

    def check_proximity_state_change(entity, old_state, new_state):
        # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """ Function to perform the proximity checking """
        entity_name = new_state.attributes['friendly_name']
        device_is_in_zone = False
        devices_to_calculate = False
        devices_in_zone = ''

        # check for devices in the monitored zone
        for device in proximity_devices:
            device_state = hass.states.get(device)

            if device_state.state not in ignored_zones:
                devices_to_calculate = True

            # check the location of all devices
            if device_state.state == config[DOMAIN]['zone']:
                device_is_in_zone = True
                device_friendly = device_state.attributes['friendly_name']
                if devices_in_zone != '':
                    devices_in_zone = devices_in_zone + ', '
                devices_in_zone = devices_in_zone + device_friendly
                _LOGGER.info('%s: %s is in the monitored zone: %s',
                             entity_name, device, device_state.state)

        # no-one to track so reset the entity
        if not devices_to_calculate:
            proximity.dist_to = 'not set'
            proximity.dir_of_travel = 'not set'
            proximity.nearest = 'not set'
            proximity.update_ha_state()
            _LOGGER.debug('%s: all devices in an ignored zone', entity_name)
            return

        # at least one device is in the monitored zone so update the entity
        if device_is_in_zone:
            proximity.dist_to = 0
            proximity.dir_of_travel = 'arrived'
            proximity.nearest = devices_in_zone
            proximity.update_ha_state()
            _LOGGER.debug('%s: update entity: distance=0: direction='
                          'arrived: device=%s', entity_name, devices_in_zone)
            return

        # we can't check proximity because latitude and longitude don't exist
        if 'latitude' not in new_state.attributes:
            _LOGGER.info('%s: not LAT or LONG current position cannot be '
                         'calculated', entity_name)
            return

        # collect distances to the zone for all devices
        distances_to_zone = {}
        for device in proximity_devices:
            # ignore devices in an ignored zone
            device_state = hass.states.get(device)
            if device_state.state in ignored_zones:
                _LOGGER.debug('%s: no need to compare with %s: device is in '
                              'ignored zone', entity_name, device)
                continue

            # ignore devices if proximity cannot be calculated
            if 'latitude' not in device_state.attributes:
                _LOGGER.debug('%s: cannot compare with %s: no location '
                              'attributes', entity_name, device)
                continue

            # calculate the distance to the proximity zone
            dist_to_zone = distance(proximity_latitude,
                                    proximity_longitude,
                                    device_state.attributes['latitude'],
                                    device_state.attributes['longitude'])

            # add the device and distance to a dictionary
            distances_to_zone[device] = round(dist_to_zone / 1000, 1)
            _LOGGER.debug('%s: distance to zone for device %s = %s',
                          entity_name, device, distances_to_zone[device])

        # loop through each of the distances collected and work out the closest
        closest_device = ''
        dist_to_zone = 1000000

        for device in distances_to_zone:
            _LOGGER.debug('%s: compare distances: device=%s: distance=%s',
                          entity_name, device, distances_to_zone[device])

            if distances_to_zone[device] < dist_to_zone:
                closest_device = device
                _LOGGER.debug('%s: closest device: device=%s: %s < %s',
                              entity_name, device, dist_to_zone,
                              distances_to_zone[device])
                dist_to_zone = distances_to_zone[device]

        # if the closest device is one of the other devices
        if closest_device != entity:
            proximity.dist_to = round(distances_to_zone[closest_device])
            proximity.dir_of_travel = 'unknown'
            proximity.nearest = closest_device
            proximity.update_ha_state()
            _LOGGER.debug('%s: update entity: distance=%s: direction='
                          'unknown: device=%s', entity_name,
                          dist_to_zone, closest_device)
            return

        # stop if we cannot calculate the direction of travel (i.e. we don't
        # have a previous state and a current LAT and LONG)
        if old_state is None or 'latitude' not in old_state.attributes:
            proximity.dist_to = round(distances_to_zone[entity])
            proximity.dir_of_travel = 'unknown'
            proximity.nearest = entity_name
            proximity.update_ha_state()
            _LOGGER.debug('%s: update entity: distance=%s: direction='
                          'unknown: device=%s', entity_id,
                          dist_to_zone, entity_name)
            _LOGGER.info('%s: cannot determine direction of travel: old '
                         'and/or new LAT or LONG are missing', entity_name)
            return

        # reset the variables
        distance_travelled = 0

        # calculate the distance travelled
        old_distance = distance(proximity_latitude, proximity_longitude,
                                old_state.attributes['latitude'],
                                old_state.attributes['longitude'])
        _LOGGER.debug('%s: old distance=%s', entity_name, old_distance)
        new_distance = distance(proximity_latitude, proximity_longitude,
                                new_state.attributes['latitude'],
                                new_state.attributes['longitude'])
        _LOGGER.debug('%s: new distance=%s', entity_name, new_distance)
        distance_travelled = round(new_distance - old_distance, 1)

        # check for tolerance
        if distance_travelled < tolerance * -1:
            direction_of_travel = 'towards'
            _LOGGER.info('%s: travelled=%s: moving=%s', entity_name,
                         distance_travelled, direction_of_travel)
        elif distance_travelled > tolerance:
            direction_of_travel = 'away_from'
            _LOGGER.info('%s: travelled=%s: moving=%s', entity_name,
                         distance_travelled, direction_of_travel)
        else:
            direction_of_travel = 'stationary'
            _LOGGER.info('%s: distance travelled too small: %s',
                         entity_name, distance_travelled)

        # update the proximity entity
        proximity.dist_to = round(dist_to_zone)
        proximity.dir_of_travel = direction_of_travel
        proximity.nearest = entity_name
        proximity.update_ha_state()
        _LOGGER.debug('%s update entity: distance=%s: direction=%s: '
                      'device=%s', entity_id, round(dist_to_zone),
                      direction_of_travel, entity_name)

        _LOGGER.info('%s: proximity calculation complete', entity_name)

    # main command to monitor proximity of devices
    track_state_change(hass, proximity_devices,
                       check_proximity_state_change)

    # Tells the bootstrapper that the component was successfully initialized
    return True


class Proximity(Entity):
    """ Represents a Proximity in Home Assistant. """
    def __init__(self, hass, zone_friendly_name, dist_to, dir_of_travel,
                 nearest):
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.friendly_name = zone_friendly_name
        self.dist_to = dist_to
        self.dir_of_travel = dir_of_travel
        self.nearest = nearest

    @property
    def state(self):
        return self.dist_to

    @property
    def state_attributes(self):
        return {
            ATTR_DIST_FROM: self.dist_to,
            ATTR_DIR_OF_TRAVEL: self.dir_of_travel,
            ATTR_NEAREST: self.nearest,
            ATTR_FRIENDLY_NAME: self.friendly_name
        }
