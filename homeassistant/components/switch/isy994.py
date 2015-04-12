""" Support for ISY994 lights. """
# system imports
import logging

# homeassistant imports
from homeassistant.components.isy994 import ISY, ISYDeviceABC
from homeassistant.const import STATE_ON, STATE_OFF


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the isy994 platform. """
    logger = logging.getLogger(__name__)
    devs = []
    # verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # import not dimmable nodes and groups
    for node in ISY.nodes:
        if not node.dimmable:
            devs.append(ISYSwitchDevice(node))
    # import ISY programs

    add_devices(devs)


class ISYSwitchDevice(ISYDeviceABC):
    """ represents as isy light within home assistant. """

    _domain = 'switch'
    _dtype = 'binary'
    _states = [STATE_ON, STATE_OFF]
