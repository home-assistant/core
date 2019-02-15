"""Support for tracking a Nissan Leaf."""
import logging

from homeassistant.components.nissan_leaf import (
    DATA_LEAF, DATA_LOCATION, SIGNAL_UPDATE_LEAF)
from homeassistant.helpers.dispatcher import dispatcher_connect
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']

ICON_CAR = "mdi:car"


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Nissan Leaf tracker."""
    _LOGGER.debug("Setting up Scanner (device_tracker) for Nissan Leaf, "
                  "discovery_info=%s", discovery_info)

    def see_vehicle():
        """Handle the reporting of the vehicle position."""
        for key, value in hass.data[DATA_LEAF].items():
            host_name = value.leaf.nickname
            dev_id = 'nissan_leaf_{}'.format(slugify(host_name))
            if not value.data[DATA_LOCATION]:
                _LOGGER.debug("No position found for vehicle %s", key)
                return False
            _LOGGER.debug("Updating device_tracker for %s with position %s",
                          value.leaf.nickname,
                          value.data[DATA_LOCATION].__dict__)
            attrs = {
                'updated_on': value.last_location_response,
            }
            see(dev_id=dev_id,
                host_name=host_name,
                gps=(
                    value.data[DATA_LOCATION].latitude,
                    value.data[DATA_LOCATION].longitude
                ),
                attributes=attrs,
                icon=ICON_CAR)

    dispatcher_connect(hass, SIGNAL_UPDATE_LEAF, see_vehicle)

    return True
