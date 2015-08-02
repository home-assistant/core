"""
homeassistant.components.switch.child_light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""

from homeassistant.components.switch.child_switch import ChildSwitch
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

    hass.states.track_change(
        discovery_info.get('parent_entity_id'), child_light.track_state)

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
