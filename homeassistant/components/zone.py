"""
Support for the definition of zones.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zone/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_HIDDEN, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_NAME, CONF_LATITUDE,
    CONF_LONGITUDE, CONF_ICON)
from homeassistant.helpers import extract_domain_configs
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.util.location import distance
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_PASSIVE = 'passive'
ATTR_RADIUS = 'radius'

CONF_PASSIVE = 'passive'
CONF_RADIUS = 'radius'

DEFAULT_NAME = 'Unnamed zone'
DEFAULT_PASSIVE = False
DEFAULT_RADIUS = 100
DOMAIN = 'zone'

ENTITY_ID_FORMAT = 'zone.{}'
ENTITY_ID_HOME = ENTITY_ID_FORMAT.format('home')

ICON_HOME = 'mdi:home'
ICON_IMPORT = 'mdi:import'

STATE = 'zoning'

# The config that zone accepts is the same as if it has platforms.
PLATFORM_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_LATITUDE): cv.latitude,
    vol.Required(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.Coerce(float),
    vol.Optional(CONF_PASSIVE, default=DEFAULT_PASSIVE): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
})


def active_zone(hass, latitude, longitude, radius=0):
    """Find the active zone for given latitude, longitude."""
    # Sort entity IDs so that we are deterministic if equal distance to 2 zones
    zones = (hass.states.get(entity_id) for entity_id
             in sorted(hass.states.entity_ids(DOMAIN)))

    min_dist = None
    closest = None

    for zone in zones:
        if zone.attributes.get(ATTR_PASSIVE):
            continue

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
    """Test if given latitude, longitude is in given zone."""
    zone_dist = distance(
        latitude, longitude,
        zone.attributes[ATTR_LATITUDE], zone.attributes[ATTR_LONGITUDE])

    return zone_dist - radius < zone.attributes[ATTR_RADIUS]


def setup(hass, config):
    """Setup zone."""
    entities = set()
    for key in extract_domain_configs(config, DOMAIN):
        entries = config[key]
        if not isinstance(entries, list):
            entries = entries,

        for entry in entries:
            name = entry.get(CONF_NAME)
            latitude = entry.get(CONF_LATITUDE)
            longitude = entry.get(CONF_LONGITUDE)
            radius = entry.get(CONF_RADIUS)
            icon = entry.get(CONF_ICON)
            passive = entry.get(CONF_PASSIVE)

            zone = Zone(
                hass, name, latitude, longitude, radius, icon, passive, False)
            add_zone(hass, name, zone, entities)
            entities.add(zone.entity_id)

    if ENTITY_ID_HOME not in entities:
        zone = Zone(hass, hass.config.location_name,
                    hass.config.latitude, hass.config.longitude,
                    DEFAULT_RADIUS, ICON_HOME, False, False)
        add_zone(hass, hass.config.location_name, zone, entities)
        zone.entity_id = ENTITY_ID_HOME
        zone.update_ha_state()

    return True


# Add a zone to the existing set
def add_zone(hass, name, zone, entities=None):
    """Add a zone from other components."""
    _LOGGER.info("Adding new zone %s", name)
    if entities is None:
        _entities = set()
    else:
        _entities = entities
    zone.entity_id = generate_entity_id(ENTITY_ID_FORMAT, name, _entities)
    zone_exists = hass.states.get(zone.entity_id)
    if zone_exists is None:
        zone.update_ha_state()
        _entities.add(zone.entity_id)
        return zone
    else:
        _LOGGER.info("Zone already exists")
        return zone_exists


class Zone(Entity):
    """Representation of a Zone."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, hass, name, latitude, longitude, radius, icon, passive,
                 imported):
        """Initialize the zone."""
        self.hass = hass
        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._radius = radius
        self._icon = icon
        self._passive = passive
        self._imported = imported

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state property really does nothing for a zone."""
        return STATE

    @property
    def icon(self):
        """Return the icon if any."""
        return self._icon

    @property
    def state_attributes(self):
        """Return the state attributes of the zone."""
        data = {
            ATTR_HIDDEN: True,
            ATTR_LATITUDE: self._latitude,
            ATTR_LONGITUDE: self._longitude,
            ATTR_RADIUS: self._radius,
        }
        if self._passive:
            data[ATTR_PASSIVE] = self._passive
        return data
