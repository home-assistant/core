""" Support for Vera lights. """
import logging
import requests
import time
import json

from homeassistant.helpers import Device
import homeassistant.external.vera.vera as veraApi
from homeassistant.const import (STATE_OPEN, STATE_CLOSED, ATTR_FRIENDLY_NAME)

_LOGGER = logging.getLogger('Vera_Sensor')

vera_controller = None
vera_sensors = []

def get_devices(hass, config):
    """ Find and return Vera Sensors. """
    try:
        base_url = config.get('vera_controller_url')
        if not base_url:
            _LOGGER.error("The required parameter 'vera_controller_url' was not found in config")
            #return False

        device_data_str = config.get('device_data')        
        device_data = None
        if device_data_str:
            try:
                device_data = json.loads(device_data_str)
            except Exception as json_ex:
                _LOGGER.error('Vera sensors error parsing device info, should be in the format [{"id" : 12, "name": "Temperature"}]: %s', json_ex)

        vera_controller = veraApi.VeraController(base_url)
        devices = vera_controller.get_devices(['Temperature Sensor', 'Light Sensor', 'Sensor'])

        vera_sensors = []
        for device in devices:
            vera_sensors.append(VeraSensor(device, get_extra_device_data(device_data, device.deviceId)))

    except Exception as inst:
        _LOGGER.error("Could not find Vera sensors: %s", inst)

    return vera_sensors

def setup_platform(hass, config, add_devices, discovery_info=None):
    add_devices(get_devices(hass, config))

def get_extra_device_data(device_data, device_id):
    if not device_data:
        return None

    for item in device_data:
        if item.get('id') == device_id:
            return item
    return None


class VeraSensor(Device):
    """ Represents a Vera Sensor """
    extra_data = None
    current_value = ''

    def __init__(self, vera_device, extra_data=None):
        self.vera_device = vera_device
        self.extra_data = extra_data        

    def __str__(self):
        return "%s %s %s" % (self.name(), self.deviceId(), self.state())

    @property
    def state(self):
        return self.current_value

    def updateState(self):
        return self.state()

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


    def update(self):
        if self.vera_device.category == "Temperature Sensor":
            self.vera_device.refresh_value('CurrentTemperature')
            self.current_value = self.vera_device.get_value('CurrentTemperature') + '°' + self.vera_device.veraController.temperature_units
        elif self.vera_device.category == "Light Sensor":
            self.vera_device.refresh_value('CurrentLevel')
            self.current_value = self.vera_device.get_value('CurrentLevel')
        elif self.vera_device.category == "Sensor":
            tripped = self.vera_device.refresh_value('Tripped')
            self.current_value = 'Tripped' if tripped == '1' else 'Not Tripped'
        else:
            self.current_value = 'Unknown'
        