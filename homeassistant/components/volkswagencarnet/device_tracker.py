"""
Support for Volkswagen Carnet Platform
"""
import logging
from homeassistant.util import slugify
from homeassistant.helpers.dispatcher import (dispatcher_connect, dispatcher_send)
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS

from . import SIGNAL_STATE_UPDATED, DATA_KEY

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Volkswagen tracker."""
    if discovery_info is None:
        return

    vin, component, attr = discovery_info
    data = hass.data[DATA_KEY]
    instrument = data.instrument(vin, component, attr)
    vehicle = instrument.vehicle

    def see_vehicle(vehicle):
        """Handle the reporting of the vehicle position."""
        host_name = data.vehicle_name(vehicle)
        dev_id = '{}'.format(slugify(host_name))
        _LOGGER.debug('Updating location of %s' % host_name)
        if instrument.state:
            see(dev_id=dev_id, host_name=host_name, source_type=SOURCE_TYPE_GPS, gps=instrument.state, icon='mdi:car')
            
    dispatcher_connect(hass, SIGNAL_STATE_UPDATED, see_vehicle)
    #dispatcher_send(hass, SIGNAL_STATE_UPDATED)
    return True
