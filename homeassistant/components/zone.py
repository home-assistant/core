"""
Support for the definition of zones.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zone/
"""
import logging

from homeassistant.const import (
    ATTR_HIDDEN, ATTR_ICON, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_NAME)
from homeassistant.helpers import extract_domain_configs
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.util.location import distance
from homeassistant.util import convert

DOMAIN = "zone"
ENTITY_ID_FORMAT = 'zone.{}'
ENTITY_ID_HOME = ENTITY_ID_FORMAT.format('home')
STATE = 'zoning'

DEFAULT_NAME = 'Unnamed zone'

ATTR_RADIUS = 'radius'
DEFAULT_RADIUS = 100

ATTR_PASSIVE = 'passive'
DEFAULT_PASSIVE = False

ICON_HOME = 'mdi:home'


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
            name = entry.get(CONF_NAME, DEFAULT_NAME)
            latitude = convert(entry.get(ATTR_LATITUDE), float)
            longitude = convert(entry.get(ATTR_LONGITUDE), float)
            radius = convert(entry.get(ATTR_RADIUS, DEFAULT_RADIUS), float)
            icon = entry.get(ATTR_ICON)
            passive = entry.get(ATTR_PASSIVE, DEFAULT_PASSIVE)

            if None in (latitude, longitude):
                logging.getLogger(__name__).error(
                    'Each zone needs a latitude and longitude.')
                continue

            zone = Zone(hass, name, latitude, longitude, radius, icon, passive)
            zone.entity_id = generate_entity_id(ENTITY_ID_FORMAT, name,
                                                entities)
            zone.update_ha_state()
            entities.add(zone.entity_id)

    if ENTITY_ID_HOME not in entities:
        zone = Zone(hass, hass.config.location_name, hass.config.latitude,
                    hass.config.longitude, DEFAULT_RADIUS, ICON_HOME, False)
        zone.entity_id = ENTITY_ID_HOME
        zone.update_ha_state()

    return True


class Zone(Entity):
    """Representation of a Zone."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, hass, name, latitude, longitude, radius, icon, passive):
        """Initialize the zone."""
        self.hass = hass
        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._radius = radius
        self._icon = icon
        self._passive = passive

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
