""" Support for ISY994 sensors. """
# system imports
import logging

# homeassistant imports
from ..isy994 import ISY
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.light import ATTR_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the isy994 platform. """
    print('************ RUNNING')
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


class ISYLightDevice(ToggleEntity):
    """ represents as isy light within home assistant. """

    domain = 'light'

    def __init__(self, node):
        # setup properties
        self.node = node
        #self.entity_id = self.domain + '.' + self.name.replace(' ', '_')

        # track changes
        self._changeHandler = self.node.status. \
                subscribe('changed', self.onUpdate)

    def __del__(self):
        self._changeHandler.unsubscribe()

    @property
    def should_poll(self):
        return False

    @property
    def dtype(self):
        return 'analog'

    @property
    def value(self):
        """ return the integer setting of the light (brightness) """
        return self.node.status._val

    @property
    def is_on(self):
        return self.value > 0

    @property
    def state_attributes(self):
        return {ATTR_BRIGHTNESS: self.value}

    @property
    def unique_id(self):
        """ Returns the id of this isy sensor """
        return self.node._id

    @property
    def name(self):
        """ Returns the name of the sensor if any. """
        return self.node.name

    def update(self):
        """ Update state of the sensor. """
        # ISY objects are automatically updated by the ISY's event stream
        pass

    def onUpdate(self, e):
        self.update_ha_state()

    def turn_on(self, **kwargs):
        """ turns the device on """
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        self.node.on(brightness)

    def turn_off(self, **kwargs):
        """ turns the device off """
        self.node.off()
