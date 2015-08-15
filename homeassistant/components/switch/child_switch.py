"""
homeassistant.components.switch.child_switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This component is designed to enable other components to create a switch
component without the nned to create an entirely new switch component.
The child switch derives its state from monitoring one of the parent
component's state attributes and will call a specified service when
toggled.

This can be especially useful when you need a switch to control some
aspect of you component.  For example a sensor you are integrating
with may have an 'armed' state that you wish to toggle.

BASIC USAGE:

You should expose the functionality you want the switch to control in your
parent component.  The child switches are created using HA's discovery
mechanism.  You simply need to define the state attribute to be montiored
and the service to be called on toggle and fire the discovery event from
your component.

from homeassistant.components.switch import (
    DISCOVER_CHILD_SWITCHES)

from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED)

...

# In your 'setup_platform' register a service

def setup_platform(hass, config, add_devices_callback, discovery_info=None):

    # setup up your component here

    ...

    # Register a service
    def toggle_something_service(service):
        my_custom_info = service.data.get('extra_data')

        # Do stuff

    hass.services.register(DOMAIN, MY_SERVICE_NAME, toggle_something_service)

# In your 'setup_platform' or from inside the component do the following:

data = {}
data['name'] = 'Arm my sensor'
data['parent_entity_id'] = self.entity_id
data['watched_variable'] = 'armed'
data['parent_domain'] = DOMAIN
data['parent_service'] = MY_SERVICE_NAME
data['parent_action'] = 'arbitrary_action_name'
data['state_attributes'] = {}
data['extra_data'] = {
    'some_usefule_id': self._device_id,
    'some_other_useful_data': '12345'}
data['initial_state'] = self._armed
self._hass.bus.fire(
    EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_CHILD_SWITCHES,
        ATTR_DISCOVERED: data})


This example will monitor the value of 'armed' in the parent component's
'state.attributes' dictionary.  The state card will ned be visible on the UI
and available to automations etc.

The 'state_attributes' is also optional but if a dictionary is passed in the
items will be added to the child sensors state attributes.

Whenever 'turn_on' or 'turn_off' are called the service specified in 'parent_service'
will be called.

The 'extra_data' field will be passed to the service in the service data dictionary
and can be very useful for establishing context in the service callback.

The ''parent_action' field is also passed back to the service when called and can
be used to distinguish between different types of service requests if necessary.

NOTES:

- At the moment this can only be created via the 'discovery' mechanism.  So do
not add it into your config file

- You need to add 'sensor' or 'child_sensor' as a dependency for your component
otherwise there is no guarantee this component will be loaded when the
discovery event fires.

"""

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID)

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
    # pylint: disable=too-many-instance-attributes
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
        attr['watched_variable'] = self._watched_variable
        attr['parent_device'] = self._parent_entity_id

        for key, value in self._extra_state_attrs.items():
            attr[key] = value

        return attr

    def track_state(self, entity_id, old_state, new_state):
        """ This is the handler called by the state change event
            when the parent device state changes """
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
