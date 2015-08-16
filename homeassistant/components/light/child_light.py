"""
homeassistant.components.light.child_light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

his component is designed to enable other components to create a light
without the nned to create an entirely new light component.
The child light derives its state from monitoring one of the parent
component's state attributes and will call a specified service when
toggled.

BASIC USAGE:

You should expose the functionality you want the light to control in your
parent component.  The child lights are created using HA's discovery
mechanism.  You simply need to define the state attribute to be montiored
and the service to be called on toggle and fire the discovery event from
your component.

from homeassistant.components.light import (
    DISCOVER_CHILD_LIGHTS)

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
data['watched_variable'] = 'brightness'
data['parent_domain'] = DOMAIN
data['parent_service'] = MY_SERVICE_NAME
data['parent_action'] = 'arbitrary_action_name'
data['state_attributes'] = {}
data['light_type'] = 'dimmer'
data['extra_data'] = {
    'some_usefule_id': self._device_id,
    'some_other_useful_data': '12345'}
data['initial_state'] = self._armed
self._hass.bus.fire(
    EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_CHILD_LIGHTS,
        ATTR_DISCOVERED: data})


This example will monitor the value of 'brightness' in the parent component's
'state.attributes' dictionary.  The state card will ned be visible on the UI
and available to automations etc.

The 'state_attributes' is also optional but if a dictionary is passed in the
items will be added to the child sensors state attributes.

Whenever 'turn_on' or 'turn_off' are called the service specified in
'parent_service' will be called.

The 'extra_data' field will be passed to the service in the service data
dictionary and can be very useful for establishing context in the service
callback.

The 'parent_action' field is also passed back to the service when called and
can be used to distinguish between different types of service requests if
necessary.

The 'light_type' field can be either 'dimmer' or 'switch' depending on the
type of light.

NOTES:

- At the moment this can only be created via the 'discovery' mechanism.  So do
not add it into your config file

- You need to add 'light' or 'child_light' as a dependency for your component
otherwise there is no guarantee this component will be loaded when the
discovery event fires.

"""

from homeassistant.components.switch.child_switch import ChildSwitch
from homeassistant.helpers import event
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_XY_COLOR)
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the lights. """
    dev = []
    child_light = ChildLight(config, discovery_info)
    dev.append(child_light)

    add_devices(dev)

    event.track_state_change(
        hass,
        discovery_info.get('parent_entity_id'),
        child_light.track_state)


class ChildLight(ChildSwitch, Light):
    """ This class is a light that can be created by another component
        it monitors the state of the parent device and calls the specified
        service when toggling is initiated """

    def __init__(self, config, discovery_info=None):
        super().__init__(config, discovery_info)
        self._xy = 0
        self._brightness = discovery_info.get('initial_brightness')
        self._light_type = discovery_info.get('light_type', 'switch')
        if self._light_type == 'dimmer':
            if self._brightness == 0:
                self._state = STATE_OFF
            else:
                self._state = STATE_ON

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    @property
    def color_xy(self):
        """ XY color value. """
        return self._xy

    def turn_on(self, **kwargs):
        """ Turn the entity on. """
        self._state = STATE_ON

        if ATTR_XY_COLOR in kwargs:
            self._xy = kwargs[ATTR_XY_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            self._brightness = 255

        self.call_parent_service()
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the entity off. """
        self._state = STATE_OFF
        if self._light_type == 'dimmer':
            self._brightness = 0

        self.call_parent_service()
        self.update_ha_state()

    def track_state(self, entity_id, old_state, new_state):
        val = new_state.attributes.get(self._watched_variable)
        if self._light_type == 'dimmer':
            self._brightness = val
            if self._brightness == 0:
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
        else:
            self._state = self.parse_watched_variable(val)

        self.update_ha_state()

    def call_parent_service(self):
        """ Calls the specified service to send state """
        service_data = {}
        service_data[ATTR_ENTITY_ID] = self._parent_entity_id
        service_data['action'] = self._parent_action
        service_data['state'] = self._state
        service_data[ATTR_XY_COLOR] = self._xy
        service_data[ATTR_BRIGHTNESS] = self._brightness
        service_data['extra_data'] = self._extra_data
        self.hass.services.call(
            self._parent_entity_domain,
            self._parent_service,
            service_data,
            blocking=True)
