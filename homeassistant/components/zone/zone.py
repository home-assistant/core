"""Zone entity and functionality."""
from homeassistant.const import ATTR_HIDDEN, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.entity import Entity
from homeassistant.util.location import distance

from .const import ATTR_PASSIVE, ATTR_RADIUS

STATE = "zoning"


def in_zone(zone, latitude, longitude, radius=0) -> bool:
    """Test if given latitude, longitude is in given zone.

    Async friendly.
    """
    zone_dist = distance(
        latitude,
        longitude,
        zone.attributes[ATTR_LATITUDE],
        zone.attributes[ATTR_LONGITUDE],
    )

    return zone_dist - radius < zone.attributes[ATTR_RADIUS]


class Zone(Entity):
    """Representation of a Zone."""

    name = None

    def __init__(self, hass, name, latitude, longitude, radius, icon, passive):
        """Initialize the zone."""
        self.hass = hass
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self._radius = radius
        self._icon = icon
        self._passive = passive

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
            ATTR_LATITUDE: self.latitude,
            ATTR_LONGITUDE: self.longitude,
            ATTR_RADIUS: self._radius,
        }
        if self._passive:
            data[ATTR_PASSIVE] = self._passive
        return data
