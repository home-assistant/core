"""
homeassistant.components.zone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allows defintion of zones in Home Assistant.

zone:
  name: School
  latitude: 32.8773367
  longitude: -117.2494053
  # Optional radius in meters (default: 100)
  radius: 250
  # Optional icon to show instead of name
  # See https://www.google.com/design/icons/
  # Example: home, work, group-work, shopping-cart, social:people
  icon: group-work

zone 2:
  name: Work
  latitude: 32.8753367
  longitude: -117.2474053

"""
import logging

from homeassistant.const import (
    ATTR_HIDDEN, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_NAME)
from homeassistant.helpers import extract_domain_configs, generate_entity_id
from homeassistant.helpers.entity import Entity
from homeassistant.util.location import distance

DOMAIN = "zone"
DEPENDENCIES = []
ENTITY_ID_FORMAT = 'zone.{}'
ENTITY_ID_HOME = ENTITY_ID_FORMAT.format('home')
STATE = 'zoning'

DEFAULT_NAME = 'Unnamed zone'

ATTR_RADIUS = 'radius'
DEFAULT_RADIUS = 100

ATTR_ICON = 'icon'
ICON_HOME = 'home'


def active_zone(hass, latitude, longitude, radius=0):
    """ Find the active zone for given latitude, longitude. """
    # Sort entity IDs so that we are deterministic if equal distance to 2 zones
    zones = (hass.states.get(entity_id) for entity_id
             in sorted(hass.states.entity_ids(DOMAIN)))

    min_dist = None
    closest = None

    for zone in zones:
        zone_dist = distance(
            latitude, longitude,
            zone.attributes[ATTR_LATITUDE], zone.attributes[ATTR_LONGITUDE])

        within_zone = zone_dist - radius < zone.attributes[ATTR_RADIUS]
        closer_zone = closest is None or zone_dist < min_dist
        smaller_zone = (zone_dist == min_dist and
                        zone.attributes[ATTR_RADIUS] <
                        closest.attributes[ATTR_RADIUS])

        if within_zone and (closer_zone or smaller_zone):
            min_dist = zone_dist
            closest = zone

    return closest


def in_zone(zone, latitude, longitude, radius=0):
    """ Test if given latitude, longitude is in given zone. """
    zone_dist = distance(
        latitude, longitude,
        zone.attributes[ATTR_LATITUDE], zone.attributes[ATTR_LONGITUDE])

    return zone_dist - radius < zone.attributes[ATTR_RADIUS]


def setup(hass, config):
    """ Setup zone. """
    entities = set()

    for key in extract_domain_configs(config, DOMAIN):
        entries = config[key]
        if not isinstance(entries, list):
            entries = entries,

        for entry in entries:
            name = entry.get(CONF_NAME, DEFAULT_NAME)
            latitude = entry.get(ATTR_LATITUDE)
            longitude = entry.get(ATTR_LONGITUDE)
            radius = entry.get(ATTR_RADIUS, DEFAULT_RADIUS)
            icon = entry.get(ATTR_ICON)

            if None in (latitude, longitude):
                logging.getLogger(__name__).error(
                    'Each zone needs a latitude and longitude.')
                continue

            zone = Zone(hass, name, latitude, longitude, radius, icon)
            zone.entity_id = generate_entity_id(ENTITY_ID_FORMAT, name,
                                                entities)
            zone.update_ha_state()
            entities.add(zone.entity_id)

    if ENTITY_ID_HOME not in entities:
        zone = Zone(hass, hass.config.location_name, hass.config.latitude,
                    hass.config.longitude, DEFAULT_RADIUS, ICON_HOME)
        zone.entity_id = ENTITY_ID_HOME
        zone.update_ha_state()

    return True


class Zone(Entity):
    """ Represents a Zone in Home Assistant. """
    # pylint: disable=too-many-arguments
    def __init__(self, hass, name, latitude, longitude, radius, icon):
        self.hass = hass
        self._name = name
        self.latitude = latitude
        self.longitude = longitude
        self.radius = radius
        self.icon = icon

    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ The state property really does nothing for a zone. """
        return STATE

    @property
    def state_attributes(self):
        attr = {
            ATTR_HIDDEN: True,
            ATTR_LATITUDE: self.latitude,
            ATTR_LONGITUDE: self.longitude,
            ATTR_RADIUS: self.radius,
        }
        if self.icon:
            attr[ATTR_ICON] = self.icon
        return attr
