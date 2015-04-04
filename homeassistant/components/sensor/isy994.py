""" Support for ISY994 sensors. """
# system imports
import logging

# homeassistant imports
from ..isy994 import ISY
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_OPEN, STATE_CLOSED


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the isy994 platform. """
    logger = logging.getLogger(__name__)
    devs = []
    # verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # import weather
    if ISY.climate is not None:
        for prop in ISY.climate._id2name:
            if prop is not None:
                devs.append(ISYSensorDevice('ISY.weather.' + prop, prop,
                    getattr(ISY.climate, prop), 
                    getattr(ISY.climate, prop + '_units')))


    add_devices(devs)


class ISYSensorDevice(Entity):
    """ represents a isy sensor within home assistant. """

    domain = 'sensor'

    def __init__(self, device_id, name, source, units=None):
        # setup properties
        self._id = device_id
        self._name = name
        self.entity_id = self.domain + '.' + self.name.replace(' ', '_')
        self._source = source
        self._units = units

        # track changes
        self._changeHandler = self._source.subscribe('changed', self.onUpdate)

    def __del__(self):
        self._changeHandler.unsubscribe()

    @property
    def should_poll(self):
        return False

    @property
    def dtype(self):
        return 'binary' if self._units is None else 'analog'

    @property
    def state(self):
        """ Returns the state. """
        if self.dtype is 'binary':
            return STATE_OPEN if self.is_open >= 255 else STATE_CLOSED
        else:
            return self.value

    @property
    def state_attributes(self):
        return {}

    @property
    def unit_of_measurement(self):
        return self._units

    @property
    def unique_id(self):
        """ Returns the id of this isy sensor """
        return self._id

    @property
    def name(self):
        """ Returns the name of the sensor if any. """
        return self._name

    def update(self):
        """ Update state of the sensor. """
        # ISY objects are automatically updated by the ISY's event stream
        pass

    @property
    def is_open(self):
        """ True if door is open. """
        return self.value >= 255

    @property
    def value(self):
        return self._source._val

    def onUpdate(self, e):
        self.update_ha_state()
