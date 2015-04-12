""" Support for ISY994 lights. """
# system imports
import logging

# homeassistant imports
from homeassistant.components.isy994 import ISYDeviceABC, ISY
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import STATE_ON, STATE_OFF


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the isy994 platform. """
    logger = logging.getLogger(__name__)
    devs = []
    # verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # import dimmable nodes
    for node in ISY.nodes:
        if node.dimmable:
            devs.append(ISYLightDevice(node))

    add_devices(devs)


class ISYLightDevice(ISYDeviceABC):
    """ represents as isy light within home assistant. """

    _domain = 'light'
    _dtype = 'analog'
    _attrs = {ATTR_BRIGHTNESS: 'value'}
    _onattrs = [ATTR_BRIGHTNESS]
    _states = [STATE_ON, STATE_OFF]
