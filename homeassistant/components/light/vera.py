"""
homeassistant.components.light.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for Vera lights. This component is useful if you wish for switches
connected to your Vera controller to appear as lights in Home Assistant.
All switches will be added as a light unless you exclude them in the config.

Configuration:

To use the Vera lights you will need to add something like the following to
your config/configuration.yaml.

light:
    platform: vera
    vera_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        12:
            name: My awesome switch
            exclude: true
        13:
            name: Another switch

Variables:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80. Example: http://192.168.1.21:3480/

device_data
*Optional
This contains an array additional device info for your Vera devices. It is not
required and if not specified all lights configured in your Vera controller
will be added with default values. You should use the id of your vera device
as the key for the device within device_data.

These are the variables for the device_data array:

name
*Optional
This parameter allows you to override the name of your Vera device in the HA
interface, if not specified the value configured for the device in your Vera
will be used.

exclude
*Optional
This parameter allows you to exclude the specified device from Home Assistant,
it should be set to "true" if you want this device excluded.

"""
import logging
from requests.exceptions import RequestException
from homeassistant.components.switch.vera import VeraSwitch
from homeassistant.components.switch.vera import VeraControllerSwitch
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.vera.vera as veraApi
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_XY_COLOR)
from homeassistant.components.controller.vera import SERVICE_SET_VAL

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """

    if discovery_info is None:

        base_url = config.get('vera_controller_url')
        if not base_url:
            _LOGGER.error(
                "The required parameter 'vera_controller_url'"
                " was not found in config"
            )
            return False

        device_data = config.get('device_data', {})

        controller = veraApi.VeraController(base_url)
        devices = []
        try:
            devices = controller.get_devices(['Switch', 'On/Off Switch'])
        except RequestException:
            # There was a network related error connecting to the vera
            _LOGGER.exception("Error communicating with Vera API")
            return False

        lights = []
        for device in devices:
            extra_data = device_data.get(device.deviceId, {})
            exclude = extra_data.get('exclude', False)

            if exclude is not True:
                lights.append(VeraSwitch(device, extra_data))

        add_devices_callback(lights)
    else:
        if not discovery_info.get('state_variable', False):
            _LOGGER.error('The "state_variable" value was not passed \
                to the Vera light in the discovery data')

        if discovery_info.get('light_type', 'switch') == 'switch':
            new_light = VeraControllerSwitch(
                hass,
                discovery_info.get('config_data', {}),
                discovery_info.get('device_data', {}),
                discovery_info)
        else:
            new_light = VeraControllerLight(
                hass,
                discovery_info.get('config_data', {}),
                discovery_info.get('device_data', {}),
                discovery_info)

        add_devices_callback([new_light])

        hass.states.track_change(
            discovery_info.get('parent_entity_id'), new_light.track_state)

        new_light.create_child_devices()


class VeraControllerLight(VeraControllerSwitch):
    """ Represents a Vera Light that is discovered by a controller entity. """

    def __init__(self, hass, config, device_data, discovery_info):
        super().__init__(hass, config, device_data, discovery_info)
        if discovery_info is None:
            discovery_info = {}
        self._xy = 0
        self._brightness = discovery_info.get('initial_brightness')
        self._light_type = discovery_info.get('light_type', 'switch')

        if self._light_type == 'dimmer':
            self._target_property = 'LoadLevelTarget'
            self._parent_action = 'dim'
            self._brightness = self.get_brightness()

            if self._brightness == 0:
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
        else:
            self._parent_action = 'switch'
            self._target_property = 'Target'

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
        """ This is the handler called by the state change event
        when the parent device state changes """
        vera_device_data = new_state.attributes.get('vera_device_data', {})
        if self._vera_device_id in vera_device_data.keys():
            self.set_device_data(
                vera_device_data.get(self._vera_device_id, {}))

        if self._light_type == 'dimmer':
            self._brightness = self.get_brightness()
            if self._brightness == 0:
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
        else:
            val = str(self._device_data.get(self._state_variable, '0'))
            if val == '1':
                self._state = STATE_ON
            else:
                self._state = STATE_OFF

        self.update_ha_state()

    def call_parent_service(self):
        """ Calls the specified service to send state """
        service_data = {}
        service_data[ATTR_ENTITY_ID] = self._parent_entity_id
        service_data['action'] = self._parent_action
        service_data['state'] = self._state
        service_data[ATTR_XY_COLOR] = self._xy
        service_data[ATTR_BRIGHTNESS] = self._brightness
        service_data['extra_data'] = {
            'vera_device_id': self._vera_device_id,
            'vera_variable': self._target_property}
        self.hass.services.call(
            self._parent_entity_domain,
            SERVICE_SET_VAL,
            service_data,
            blocking=True)
