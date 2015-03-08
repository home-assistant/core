"""
Support for Vera switches.

Configuration:
To use the Vera lights you will need to add something like the following to
your config/configuration.yaml

switch:
    platform: vera
    vera_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        -
            vera_id: 12
            name: My awesome switch
            exclude: true
        -
            vera_id: 13
            name: Another Switch

VARIABLES:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80
Example: http://192.168.1.21:3480/


device_data
*Optional
This contains an array additional device info for your Vera devices.  It is not
required and if not specified all lights configured in your Vera controller
will be added with default values.


These are the variables for the device_data array:

vera_id
*Required
The Vera device id you wish these configuration options to be applied to


name
*Optional
This parameter allows you to override the name of your Vera device in the HA
interface, if not specified the value configured for the device in your Vera
will be used


exclude
*Optional
This parameter allows you to exclude the specified device from homeassistant,
it should be set to "true" if you want this device excluded

"""
import logging
import time

from homeassistant.helpers import ToggleDevice
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.vera.vera as veraApi

_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Vera switches. """
    try:
        base_url = config.get('vera_controller_url')
        if not base_url:
            _LOGGER.error("The required parameter 'vera_controller_url'"
            " was not found in config")
            return False

        device_data = config.get('device_data', None)

        vera_controller = veraApi.VeraController(base_url)
        devices = vera_controller.get_devices(['Switch', 'Armable Sensor'])

        vera_switches = []
        for device in devices:
            extra_data = get_extra_device_data(device_data, device.deviceId)
            exclude = False
            if extra_data:
                exclude = extra_data.get('exclude', False)

            if exclude is not True:
                vera_switches.append(VeraSwitch(device, extra_data))

    # pylint: disable=broad-except
    except Exception as inst:
        _LOGGER.error("Could not find Vera switches: %s", inst)
        return False

    return vera_switches

def get_extra_device_data(device_data, device_id):
    """ Gets the additional configuration data by Vera device Id """
    if not device_data:
        return None

    for item in device_data:
        if item.get('vera_id') == device_id:
            return item
    return None


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Vera lights. """
    add_devices(get_devices(hass, config))

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
            last_tripped = self.vera_device.refresh_value('LastTrip')
            trip_time_str = time.strftime("%Y-%m-%d %H:%M",
            time.localtime(int(last_tripped)))

            attr['Last Tripped'] = trip_time_str

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
        