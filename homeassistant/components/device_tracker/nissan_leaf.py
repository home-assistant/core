"""
Support for tracking a Nissan Leaf.
For more details about this platform, please refer to the documentation
of the main platform component
"""
import logging
from homeassistant.util import slugify
from homeassistant.helpers.dispatcher import (
    dispatcher_connect, dispatcher_send)
from .. import nissan_leaf as leaf_core

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['nissan_leaf']

def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Nissan Leaf tracker."""
    _LOGGER.debug("Setting up Scanner (device_tracker) for Nissan Leaf")
    
    def see_vehicle():
        """Handle the reporting of the vehicle position."""

        for key, value in hass.data[leaf_core.DATA_LEAF].items():
            host_name = value.leaf.nickname
            dev_id = 'nissan_leaf_{}'.format(slugify(host_name))
            if value.data[leaf_core.DATA_LOCATION] in [None,False]:
                _LOGGER.debug("No position found for vehicle %s", key)
                return False
            _LOGGER.debug("Updating device_tracker for %s with position %s", value.leaf.nickname, value.data[leaf_core.DATA_LOCATION])
            see(dev_id=dev_id,
                host_name=host_name,
                gps=(value.data[leaf_core.DATA_LOCATION].latitude,
                     value.data[leaf_core.DATA_LOCATION].longitude),
                icon='mdi:car')

    dispatcher_connect(hass, leaf_core.SIGNAL_UPDATE_LEAF, see_vehicle)
    dispatcher_send(hass, leaf_core.SIGNAL_UPDATE_LEAF)

    return True
