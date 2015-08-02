"""
homeassistant.components.sensor.child_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""

from homeassistant.helpers.entity import Entity

import logging

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """

    dev = []
    child_sensor = ChildSensor(config, discovery_info)
    dev.append(child_sensor)

    add_devices(dev)

    hass.states.track_change(
        discovery_info.get('parent_entity_id'), child_sensor.track_state)


class ChildSensor(Entity):
    """ A Child sensor """

    def __init__(self, config, discovery_info=None):
        self._name = discovery_info.get('name')
        self._parent_entity_id = discovery_info.get('parent_entity_id')
        self._state = discovery_info.get('initial_state')
        self._unit_of_measurement = discovery_info.get('unit_of_measurement')
        self._watched_variable = discovery_info.get('watched_variable')
        self._extra_state_attrs = discovery_info.get('state_attributes', {})

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def should_poll(self):
        """
        Polling is not required as state is updated from the parent
        """
        return False

    @property
    def state_attributes(self):
        attr = super().state_attributes
        attr['parent_device'] = self._parent_entity_id

        for key, value in self._extra_state_attrs.items():
            attr[key] = value

        return attr

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    def track_state(self, entity_id, old_state, new_state):
        if self._state != new_state:
            self._state = new_state.attributes.get(self._watched_variable)
            self.update_ha_state()

