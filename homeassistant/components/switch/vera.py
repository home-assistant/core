"""
homeassistant.components.switch.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera switches.

Configuration:
To use the Vera lights you will need to add something like the following to
your config/configuration.yaml.

switch:
    platform: vera
    vera_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        12:
            name: My awesome switch
            exclude: true
        13:
            name: Another Switch

Variables:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80. Example: http://192.168.1.21:3480/

device_data
*Optional
This contains an array additional device info for your Vera devices.  It is not
required and if not specified all lights configured in your Vera controller
will be added with default values.  You should use the id of your vera device
as the key for the device within device_data.

These are the variables for the device_data array:

name
*Optional
This parameter allows you to override the name of your Vera device in the HA
interface, if not specified the value configured for the device in your Vera
will be used.

exclude
*Optional
This parameter allows you to exclude the specified device from homeassistant,
it should be set to "true" if you want this device excluded.
"""
import logging
import time
from homeassistant.helpers import event
from requests.exceptions import RequestException
import homeassistant.util.dt as dt_util
from homeassistant.components.controller.vera import VeraControllerDevice
from homeassistant.components.controller.vera import SERVICE_SET_VAL

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TRIPPED, ATTR_ARMED, ATTR_LAST_TRIP_TIME,
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID)
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.vera.vera as veraApi

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Vera switches. """

    base_url = config.get('vera_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', {})

    vera_controller = veraApi.VeraController(base_url)
    devices = []
    try:
        devices = vera_controller.get_devices([
            'Switch', 'Armable Sensor', 'On/Off Switch'])
    except RequestException:
        # There was a network related error connecting to the vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        return False

    vera_switches = []
    for device in devices:
        extra_data = device_data.get(device.deviceId, {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True:
            vera_switches.append(VeraSwitch(device, extra_data))

    return vera_switches


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Vera lights. """
    if discovery_info is None:
        add_devices(get_devices(hass, config))
    else:
        if not discovery_info.get('state_variable', False):
            _LOGGER.error('The "state_variable" value was not passed \
                to the Vera switch in the discovery data')

        new_switch = VeraControllerSwitch(
            hass,
            discovery_info.get('config_data', {}),
            discovery_info.get('device_data', {}),
            discovery_info)
        add_devices([new_switch])

        event.track_state_change(
            hass,
            discovery_info.get('parent_entity_id'),
            new_switch.track_state)

        new_switch.create_child_devices()


class VeraSwitch(ToggleEntity):
    """ Represents a Vera Switch. """

    def __init__(self, vera_device, extra_data=None):
        self.vera_device = vera_device
        self.extra_data = extra_data
        if self.extra_data and self.extra_data.get('name'):
            self._name = self.extra_data.get('name')
        else:
            self._name = self.vera_device.name
        self.is_on_status = False
        # for debouncing status check after command is sent
        self.last_command_send = 0

    @property
    def name(self):
        """ Get the mame of the switch. """
        return self._name

    @property
    def state_attributes(self):
        attr = super().state_attributes

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.refresh_value('Armed')
            attr[ATTR_ARMED] = 'True' if armed == '1' else 'False'

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.refresh_value('LastTrip')
            if last_tripped is not None:
                utc_time = dt_util.utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = dt_util.datetime_to_str(
                    utc_time)
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.refresh_value('Tripped')
            attr[ATTR_TRIPPED] = 'True' if tripped == '1' else 'False'

        attr['Vera Device Id'] = self.vera_device.vera_device_id

        return attr

    def turn_on(self, **kwargs):
        self.last_command_send = time.time()
        self.vera_device.switch_on()
        self.is_on_status = True

    def turn_off(self, **kwargs):
        self.last_command_send = time.time()
        self.vera_device.switch_off()
        self.is_on_status = False

    @property
    def is_on(self):
        """ True if device is on. """
        return self.is_on_status

    def update(self):
        # We need to debounce the status call after turning switch on or off
        # because the vera has some lag in updating the device status
        if (self.last_command_send + 5) < time.time():
            self.is_on_status = self.vera_device.is_switched_on()


class VeraControllerSwitch(ToggleEntity, VeraControllerDevice):
    """ Represents a Vera Switch that is discovered by a controller entity. """

    def __init__(self, hass, config, device_data, discovery_info=None):
        super().__init__(hass, config, device_data)
        if discovery_info is None:
            discovery_info = {}
        self._state_variable = discovery_info.get('state_variable', None)
        self._vera_device_id = self._config.get(
            'vera_id',
            self._device_data.get('id'))
        self._parent_entity_id = discovery_info.get('parent_entity_id', None)
        self._parent_entity_domain = discovery_info.get(
            'parent_entity_domain', None)

        val = str(self._device_data.get(self._state_variable, '0'))
        if val == '1':
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    @property
    def state(self):
        """ Return the state value for this device """
        return self._state

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
        service_data['action'] = 'switch'
        service_data['state'] = self._state
        service_data['extra_data'] = {
            'vera_device_id': self._vera_device_id,
            'vera_variable': 'Target'}
        self.hass.services.call(
            self._parent_entity_domain,
            SERVICE_SET_VAL,
            service_data,
            blocking=True)

    def track_state(self, entity_id, old_state, new_state):
        """ This is the handler called by the state change event
            when the parent device state changes """
        vera_device_data = new_state.attributes.get('vera_device_data', {})
        if self._vera_device_id in vera_device_data.keys():
            self.set_device_data(
                vera_device_data.get(self._vera_device_id, {}))
        val = str(self._device_data.get(self._state_variable, '0'))
        if val == '1':
            self._state = STATE_ON
        else:
            self._state = STATE_OFF
