"""Component entity and functionality."""

from homeassistant.const import ATTR_HIDDEN, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.entity import Entity
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.location import distance

from .const import DOMAIN

ATTR_PASSIVE = 'passive'
ATTR_RADIUS = 'radius'

STATE = 'zoning'


@bind_hass
def active_zone(hass, latitude, longitude, radius=0):
    """Find the active zone for given latitude, longitude."""
    return run_callback_threadsafe(
        hass.loop, async_active_zone, hass, latitude, longitude, radius
    ).result()


@bind_hass
def async_active_zone(hass, latitude, longitude, radius=0):
    """Find the active zone for given latitude, longitude.

    This method must be run in the event loop.
    """
    # Sort entity IDs so that we are deterministic if equal distance to 2 zones
    zones = (hass.states.get(entity_id) for entity_id
             in sorted(hass.states.async_entity_ids(DOMAIN)))

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
    """Test if given latitude, longitude is in given zone.

    Async friendly.
    """
    zone_dist = distance(
        latitude, longitude,
        zone.attributes[ATTR_LATITUDE], zone.attributes[ATTR_LONGITUDE])

    return zone_dist - radius < zone.attributes[ATTR_RADIUS]


class Zone(Entity):
    """Representation of a Zone."""

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
