"""Helper methods for travel_time integrations."""
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import State


def get_location_from_attributes(entity: State) -> str:
    """Get the lat/long string from an entities attributes."""
    attr = entity.attributes
    return "{},{}".format(attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))
