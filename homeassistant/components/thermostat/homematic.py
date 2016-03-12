"""
Support for Homematic (HM-TC-IT-WM-W-EU, HM-CC-RT-DN) thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.homematic/
"""
import logging
import socket
from xmlrpc.client import ServerProxy

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELCIUS

REQUIREMENTS = []

CONF_ADDRESS = 'address'
CONF_DEVICES = 'devices'
CONF_ID = 'id'
PROPERTY_SET_TEMPERATURE = 'SET_TEMPERATURE'
PROPERTY_VALVE_STATE = 'VALVE_STATE'
PROPERTY_ACTUAL_TEMPERATURE = 'ACTUAL_TEMPERATURE'
PROPERTY_BATTERY_STATE = 'BATTERY_STATE'
PROPERTY_CONTROL_MODE = 'CONTROL_MODE'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Homematic thermostat."""
    devices = []
    try:
        homegear = ServerProxy(config[CONF_ADDRESS])
        for name, device_cfg in config[CONF_DEVICES].items():
            # get device description to detect the type
            device_type = homegear.getDeviceDescription(
                device_cfg[CONF_ID] + ':-1')['TYPE']

            if device_type in ['HM-CC-RT-DN', 'HM-CC-RT-DN-BoM']:
                devices.append(HomematicThermostat(homegear,
                                                   device_cfg[CONF_ID],
                                                   name, 4))
            elif device_type == 'HM-TC-IT-WM-W-EU':
                devices.append(HomematicThermostat(homegear,
                                                   device_cfg[CONF_ID],
                                                   name, 2))
            else:
                raise ValueError(
                    "Device Type '{}' currently not supported".format(
                        device_type))
    except socket.error:
        _LOGGER.exception("Connection error to homematic web service")
        return False

    add_devices(devices)

    return True


# pylint: disable=too-many-instance-attributes
class HomematicThermostat(ThermostatDevice):
    """Representation of a Homematic thermostat."""

    def __init__(self, device, _id, name, channel):
        """Initialize the thermostat."""
        self.device = device
        self._id = _id
        self._channel = channel
        self._name = name
        self._full_device_name = '{}:{}'.format(self._id, self._channel)

        self._current_temperature = None
        self._target_temperature = None
        self._valve = None
        self._battery = None
        self._mode = None
        self.update()

    @property
    def name(self):
        """Return the name of the Homematic device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELCIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, temperature):
        """Set new target temperature."""
        self.device.setValue(self._full_device_name,
                             PROPERTY_SET_TEMPERATURE,
                             temperature)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {"valve": self._valve,
                "battery": self._battery,
                "mode": self._mode}

    def update(self):
        """Update the data from the thermostat."""
        try:
            self._current_temperature = self.device.getValue(
                self._full_device_name,
                PROPERTY_ACTUAL_TEMPERATURE)
            self._target_temperature = self.device.getValue(
                self._full_device_name,
                PROPERTY_SET_TEMPERATURE)
            self._valve = self.device.getValue(self._full_device_name,
                                               PROPERTY_VALVE_STATE)
            self._battery = self.device.getValue(self._full_device_name,
                                                 PROPERTY_BATTERY_STATE)
            self._mode = self.device.getValue(self._full_device_name,
                                              PROPERTY_CONTROL_MODE)
        except socket.error:
            _LOGGER.exception("Did not receive any temperature data from the "
                              "homematic API.")
