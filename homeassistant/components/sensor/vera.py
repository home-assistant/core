"""
homeassistant.components.sensor.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for Vera sensors.

Configuration:

To use the Vera sensors you will need to add something like the following to
your config/configuration.yaml

sensor:
    platform: vera
    vera_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        12:
            name: My awesome sensor
            exclude: true
        13:
            name: Another sensor

Variables:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80
Example: http://192.168.1.21:3480/


device_data
*Optional
This contains an array additional device info for your Vera devices.  It is not
required and if not specified all sensors configured in your Vera controller
will be added with default values.  You should use the id of your vera device
as the key for the device within device_data

These are the variables for the device_data array:

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
from requests.exceptions import RequestException
import homeassistant.util.dt as dt_util

from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TRIPPED, ATTR_ARMED, ATTR_LAST_TRIP_TIME,
    TEMP_CELCIUS, TEMP_FAHRENHEIT)
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.vera.vera as veraApi

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Vera Sensors. """

    base_url = config.get('vera_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', {})

    vera_controller = veraApi.VeraController(base_url)
    categories = ['Temperature Sensor', 'Light Sensor', 'Sensor']
    devices = []
    try:
        devices = vera_controller.get_devices(categories)
    except RequestException:
        # There was a network related error connecting to the vera controller
        _LOGGER.exception("Error communicating with Vera API")
        return False

    vera_sensors = []
    for device in devices:
        extra_data = device_data.get(device.deviceId, {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True:
            vera_sensors.append(VeraSensor(device, extra_data))

    return vera_sensors


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Performs setup for Vera controller devices. """
    add_devices(get_devices(hass, config))


class VeraSensor(Entity):
    """ Represents a Vera Sensor. """

    def __init__(self, vera_device, extra_data=None):
        self.vera_device = vera_device
        self.extra_data = extra_data
        if self.extra_data and self.extra_data.get('name'):
            self._name = self.extra_data.get('name')
        else:
            self._name = self.vera_device.name
        self.current_value = ''
        self._temperature_units = None

    def __str__(self):
        return "%s %s %s" % (self.name, self.vera_device.deviceId, self.state)

    @property
    def state(self):
        return self.current_value

    @property
    def name(self):
        """ Get the mame of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._temperature_units

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

    def update(self):
        if self.vera_device.category == "Temperature Sensor":
            self.vera_device.refresh_value('CurrentTemperature')
            current_temp = self.vera_device.get_value('CurrentTemperature')
            vera_temp_units = self.vera_device.veraController.temperature_units

            if vera_temp_units == 'F':
                self._temperature_units = TEMP_FAHRENHEIT
            else:
                self._temperature_units = TEMP_CELCIUS

            if self.hass:
                temp = self.hass.config.temperature(
                    current_temp,
                    self._temperature_units)

                current_temp, self._temperature_units = temp

            self.current_value = current_temp
        elif self.vera_device.category == "Light Sensor":
            self.vera_device.refresh_value('CurrentLevel')
            self.current_value = self.vera_device.get_value('CurrentLevel')
        elif self.vera_device.category == "Sensor":
            tripped = self.vera_device.refresh_value('Tripped')
            self.current_value = 'Tripped' if tripped == '1' else 'Not Tripped'
        else:
            self.current_value = 'Unknown'
