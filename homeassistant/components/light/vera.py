""" Support for Vera lights. """
import logging
import requests
import time
import json

from homeassistant.helpers import ToggleDevice
import homeassistant.external.vera.vera as veraApi

_LOGGER = logging.getLogger('Vera_Light')


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    try:
        base_url = config.get('vera_controller_url')
        if not base_url:
            _LOGGER.error("The required parameter 'vera_controller_url' was not found in config")
            return False

        device_data_str = config.get('device_data')        
        device_data = None
        if device_data_str:
            try:
                device_data = json.loads(device_data_str)
            except Exception as json_ex:
                _LOGGER.error('Vera lights error parsing device info, should be in the format [{"id" : 12, "name": "Lounge Light"}]: %s', json_ex)

        controller = veraApi.VeraController(base_url)
        devices = controller.get_devices('Switch')

        lights = []
        for device in devices:
            if is_switch_a_light(device_data, device.deviceId):
                lights.append(VeraLight(device, get_extra_device_data(device_data, device.deviceId)))

        add_devices_callback(lights)
    except Exception as inst:
        _LOGGER.error("Could not find Vera lights: %s", inst)
        return False

# If you have z-wave switches that control lights you can configure them
# to be treated as lights using the "device_data" parameter in the config.
# If "device_data" is not set then all switches are treated as lights
def is_switch_a_light(device_data, device_id):
    if not device_data:
        return True

    for item in device_data:
        if item.get('id') == device_id:
            return True

    return False

def get_extra_device_data(device_data, device_id):
    if not device_data:
        return None

    for item in device_data:
        if item.get('id') == device_id:
            return item

    return None


class VeraLight(ToggleDevice):
    """ Represents a Vera light """
    is_on_status = False
    #for debouncing status check after command is sent
    last_command_send = 0
    extra_data = None

    def __init__(self, vera_device, extra_data=None):
        self.vera_device = vera_device
        self.extra_data = extra_data

    @property
    def unique_id(self):
        """ Returns the id of this light """
        return "{}.{}".format(
            self.__class__, self.info.get('uniqueid', self.name))

    @property
    def name(self):
        """ Get the mame of the light. """
        if self.extra_data and self.extra_data.get('name'):
            return self.extra_data.get('name')
        return self.vera_device.name

    @property
    def state_attributes(self):
        attr = super().state_attributes

        if self.vera_device.has_battery:
            attr['Battery'] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.refresh_value('Armed')
            attr['Armed'] = 'True' if armed == '1' else 'False'

        if self.vera_device.is_trippable:
            lastTripped = self.vera_device.refresh_value('LastTrip')
            tripTimeStr = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(lastTripped)))
            attr['Last Tripped'] = tripTimeStr

            tripped = self.vera_device.refresh_value('Tripped')
            attr['Tripped'] = 'True' if tripped == '1' else 'False'

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
        self.update()
        return self.is_on_status

    def update(self):
        # We need to debounce the status call after turning light on or off 
        # because the vera has some lag in updating the device status
        if (self.last_command_send + 5) < time.time():
            self.is_on_status = self.vera_device.is_switched_on()
        