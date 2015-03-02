""" Support for Vera lights. """
import logging
import requests
import time
import json

from homeassistant.helpers import ToggleDevice
import homeassistant.external.vera.vera as veraApi

_LOGGER = logging.getLogger('Vera_Switch')

vera_controller = None
vera_switches = []

def get_devices(hass, config):
    """ Find and return Vera switches. """
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
                _LOGGER.error('Vera switch error parsing device info, should be in the format [{"id" : 12, "name": "Lounge Light"}]: %s', json_ex)

        vera_controller = veraApi.VeraController(base_url)
        devices = vera_controller.get_devices(['Switch', 'Armable Sensor'])

        vera_switches = []
        for device in devices:
            vera_switches.append(VeraSwitch(device, get_extra_device_data(device_data, device.deviceId)))

    except Exception as inst:
        _LOGGER.error("Could not find Vera switches: %s", inst)
        return False

    return vera_switches

def get_extra_device_data(device_data, device_id):
    if not device_data:
        return None

    for item in device_data:
        if item.get('id') == device_id:
            return item
    return None


def get_switches():
    return vera_switches


class VeraSwitch(ToggleDevice):
    """ Represents a Vera Switch """
    is_on_status = False
    #for debouncing status check after command is sent
    last_command_send = 0
    extra_data = None

    def __init__(self, vera_device, extra_data=None):
        self.vera_device = vera_device
        self.extra_data = extra_data

    @property
    def unique_id(self):
        """ Returns the id of this switch """
        return "{}.{}".format(
            self.__class__, self.info.get('uniqueid', self.name))

    @property
    def name(self):
        """ Get the mame of the switch. """
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
        # We need to debounce the status call after turning switch on or off 
        # because the vera has some lag in updating the device status
        if (self.last_command_send + 5) < time.time():
            self.is_on_status = self.vera_device.is_switched_on()
        