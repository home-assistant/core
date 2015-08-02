"""
homeassistant.components.switch.child_switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    STATE_ON, STATE_OFF,ATTR_ENTITY_ID)

import logging

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """

    dev = []
    child_switch = ChildSwitch(config, discovery_info)
    dev.append(child_switch)

    add_devices(dev)

    hass.states.track_change(
        discovery_info.get('parent_entity_id'), child_switch.track_state)


class ChildSwitch(ToggleEntity):
    """ A Child switch """

    def __init__(self, config, discovery_info=None):
        self._name = discovery_info.get('name')
        self._parent_entity_id = discovery_info.get('parent_entity_id')
        self._watched_variable = discovery_info.get('watched_variable')
        self._state = self.parse_watched_variable(discovery_info.get('initial_state'))
        self._parent_service = discovery_info.get('parent_service')
        self._parent_action = discovery_info.get('parent_action')
        self._parent_entity_domain = discovery_info.get('parent_domain')
        self._extra_data = discovery_info.get('extra_data')
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

    def track_state(self, entity_id, old_state, new_state):
        val = new_state.attributes.get(self._watched_variable)
        self._state = self.parse_watched_variable(val)
        self.update_ha_state()

    def parse_watched_variable(self, val):
        """ Convert the raw state value into a switch state """
        if val == STATE_ON or val == '1' or val == 1 or val == True or val == 'True':
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def is_on(self):
        """ True if entity is on. """
        return True if self._state == STATE_ON else False

    def turn_on(self, **kwargs):
        """ Turn the entity on. """
        self._state = STATE_ON
        self.call_parent_service()
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the entity off. """
        self._state = STATE_OFF
        self.call_parent_service()
        self.update_ha_state()

    def call_parent_service(self):
        """ Calls the specified service to send state """
        service_data = {}
        service_data[ATTR_ENTITY_ID] = self._parent_entity_id
        service_data['action'] = self._parent_action
        service_data['state'] = self._state
        service_data['extra_data'] = self._extra_data
        self.hass.services.call(
            self._parent_entity_domain,
            self._parent_service,
            service_data,
            blocking=True)
