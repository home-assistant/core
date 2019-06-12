"""Support for tracking a Nissan Leaf."""
import logging

from homeassistant.helpers.dispatcher import dispatcher_connect
from homeassistant.util import slugify

from . import DATA_LEAF, DATA_LOCATION, SIGNAL_UPDATE_LEAF

_LOGGER = logging.getLogger(__name__)

ICON_CAR = "mdi:car"


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Nissan Leaf tracker."""
    if discovery_info is None:
        return False

    def see_vehicle():
        """Handle the reporting of the vehicle position."""
        for vin, datastore in hass.data[DATA_LEAF].items():
            host_name = datastore.leaf.nickname
            dev_id = 'nissan_leaf_{}'.format(slugify(host_name))
            if not datastore.data[DATA_LOCATION]:
                _LOGGER.debug("No position found for vehicle %s", vin)
                return
            _LOGGER.debug("Updating device_tracker for %s with position %s",
                          datastore.leaf.nickname,
                          datastore.data[DATA_LOCATION].__dict__)
            attrs = {
                'updated_on': datastore.last_location_response,
            }
            see(dev_id=dev_id,
                host_name=host_name,
                gps=(
                    datastore.data[DATA_LOCATION].latitude,
                    datastore.data[DATA_LOCATION].longitude
                ),
                attributes=attrs,
                icon=ICON_CAR)

    dispatcher_connect(hass, SIGNAL_UPDATE_LEAF, see_vehicle)

    return True
