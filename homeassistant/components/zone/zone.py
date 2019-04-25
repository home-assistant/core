"""Zone entity and functionality."""
from homeassistant.const import ATTR_HIDDEN, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.entity import Entity
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.location import distance

from .const import DOMAIN

ATTR_PASSIVE = 'passive'
ATTR_RADIUS = 'radius'
ATTR_AREA_THRESHOLD = 'area_threshold'
ATTR_ACCURACY_THRESHOLD = 'accuracy_threshold'

STATE = 'zoning'


@bind_hass
def active_zone(hass, latitude, longitude, radius=0):
    """Find the active zone for given latitude, longitude."""
    return run_callback_threadsafe(
        hass.loop, async_active_zone, hass, latitude, longitude, radius
    ).result()


@bind_hass
def async_active_zone(hass, latitude, longitude, accuracy_radius=0):
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

        within_zone = in_zone(zone, latitude, longitude, accuracy_radius)
        closer_zone = closest is None or zone_dist < min_dist
        smaller_zone = (zone_dist == min_dist and
                        zone.attributes[ATTR_RADIUS] <
                        closest.attributes[ATTR_RADIUS])

        if within_zone and (closer_zone or smaller_zone):
            min_dist = zone_dist
            closest = zone

    return closest


def in_zone(zone, latitude, longitude, accuracy_radius=0) -> bool:
    """Test if given latitude, longitude is in given zone.

    Async friendly.
    """
    zone_dist = distance(
        latitude, longitude,
        zone.attributes[ATTR_LATITUDE], zone.attributes[ATTR_LONGITUDE])

    if ATTR_ACCURACY_THRESHOLD in zone.attributes and \
       accuracy_radius > zone.attributes[ATTR_ACCURACY_THRESHOLD]:
        return False

    if ATTR_AREA_THRESHOLD in zone.attributes:
        import math

        intersection_area = circles_intersection_area(
            zone_dist,
            accuracy_radius,
            zone.attributes[ATTR_RADIUS]
        )

        entity_circle_area = math.pi * accuracy_radius ** 2

        intersection_fraction = intersection_area / entity_circle_area

        return intersection_fraction >= zone.attributes[ATTR_AREA_THRESHOLD]

    return zone_dist < accuracy_radius + zone.attributes[ATTR_RADIUS]


def circles_intersection_area(centers_distance, radius1, radius2) -> float:
    """Return the area of intersection of two circles."""
    import math

    if centers_distance <= abs(radius1 - radius2):
        # One circle is entirely enclosed in the other.
        return math.pi * min(radius1, radius2) ** 2
    if centers_distance >= radius2 + radius1:
        # The circles don't overlap at all.
        return 0

    r2_2, r1_2, d_2 = radius2 ** 2, radius1 ** 2, centers_distance ** 2
    alpha = math.acos((d_2 + r2_2 - r1_2) / (2 * centers_distance * radius2))
    beta = math.acos((d_2 + r1_2 - r2_2) / (2 * centers_distance * radius1))
    return (
        r2_2 * alpha + r1_2 * beta -
        0.5 * (r2_2 * math.sin(2*alpha) + r1_2 * math.sin(2*beta))
    )


class Zone(Entity):
    """Representation of a Zone."""

    def __init__(self, hass, name, latitude, longitude, radius, icon, passive,
                 area_threshold=None, accuracy_threshold=None):
        """Initialize the zone."""
        self.hass = hass
        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._radius = radius
        self._icon = icon
        self._passive = passive
        self._area_threshold = area_threshold
        self._accuracy_threshold = accuracy_threshold

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
        if self._area_threshold:
            data[ATTR_AREA_THRESHOLD] = self._area_threshold
        if self._accuracy_threshold:
            data[ATTR_ACCURACY_THRESHOLD] = self._accuracy_threshold
        return data
