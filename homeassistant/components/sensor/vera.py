"""
homeassistant.components.sensor.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.vera/
"""
import logging
from requests.exceptions import RequestException
import homeassistant.util.dt as dt_util

from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TRIPPED, ATTR_ARMED, ATTR_LAST_TRIP_TIME,
    TEMP_CELCIUS, TEMP_FAHRENHEIT)

REQUIREMENTS = ['https://github.com/pavoni/home-assistant-vera-api/archive/'
                'efdba4e63d58a30bc9b36d9e01e69858af9130b8.zip'
                '#python-vera==0.1.1']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Vera Sensors. """
    import pyvera as veraApi

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
        attr = {}
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
