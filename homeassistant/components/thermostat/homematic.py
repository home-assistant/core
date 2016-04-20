"""
Support for Homematic (HM-TC-IT-WM-W-EU, HM-CC-RT-DN) thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.homematic/
"""
import logging
import socket
from xmlrpc.client import ServerProxy
from xmlrpc.client import Error
from collections import namedtuple

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.temperature import convert

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_ADDRESS = 'address'
CONF_DEVICES = 'devices'
CONF_ID = 'id'
PROPERTY_SET_TEMPERATURE = 'SET_TEMPERATURE'
PROPERTY_VALVE_STATE = 'VALVE_STATE'
PROPERTY_ACTUAL_TEMPERATURE = 'ACTUAL_TEMPERATURE'
PROPERTY_BATTERY_STATE = 'BATTERY_STATE'
PROPERTY_LOWBAT = 'LOWBAT'
PROPERTY_CONTROL_MODE = 'CONTROL_MODE'
PROPERTY_BURST_MODE = 'BURST_RX'
TYPE_HM_THERMOSTAT = 'HOMEMATIC_THERMOSTAT'
TYPE_HM_WALLTHERMOSTAT = 'HOMEMATIC_WALLTHERMOSTAT'
TYPE_MAX_THERMOSTAT = 'MAX_THERMOSTAT'

HomematicConfig = namedtuple('HomematicConfig',
                             ['device_type',
                              'platform_type',
                              'channel',
                              'maint_channel'])

HM_TYPE_MAPPING = {
    'HM-CC-RT-DN': HomematicConfig('HM-CC-RT-DN',
                                   TYPE_HM_THERMOSTAT,
                                   4, 4),
    'HM-CC-RT-DN-BoM': HomematicConfig('HM-CC-RT-DN-BoM',
                                       TYPE_HM_THERMOSTAT,
                                       4, 4),
    'HM-TC-IT-WM-W-EU': HomematicConfig('HM-TC-IT-WM-W-EU',
                                        TYPE_HM_WALLTHERMOSTAT,
                                        2, 2),
    'BC-RT-TRX-CyG': HomematicConfig('BC-RT-TRX-CyG',
                                     TYPE_MAX_THERMOSTAT,
                                     1, 0),
    'BC-RT-TRX-CyG-2': HomematicConfig('BC-RT-TRX-CyG-2',
                                       TYPE_MAX_THERMOSTAT,
                                       1, 0),
    'BC-RT-TRX-CyG-3': HomematicConfig('BC-RT-TRX-CyG-3',
                                       TYPE_MAX_THERMOSTAT,
                                       1, 0)
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Homematic thermostat."""
    devices = []
    try:
        address = config[CONF_ADDRESS]
        homegear = ServerProxy(address)

        for name, device_cfg in config[CONF_DEVICES].items():
            # get device description to detect the type
            device_type = homegear.getDeviceDescription(
                device_cfg[CONF_ID] + ':-1')['TYPE']

            if device_type in HM_TYPE_MAPPING.keys():
                devices.append(HomematicThermostat(
                    HM_TYPE_MAPPING[device_type],
                    address,
                    device_cfg[CONF_ID],
                    name))
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

    def __init__(self, hm_config, address, _id, name):
        """Initialize the thermostat."""
        self._hm_config = hm_config
        self.address = address
        self._id = _id
        self._name = name
        self._full_device_name = '{}:{}'.format(self._id,
                                                self._hm_config.channel)
        self._maint_device_name = '{}:{}'.format(self._id,
                                                 self._hm_config.maint_channel)
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
        return TEMP_CELSIUS

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
        device = ServerProxy(self.address)
        device.setValue(self._full_device_name,
                        PROPERTY_SET_TEMPERATURE,
                        temperature)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {"valve": self._valve,
                "battery": self._battery,
                "mode": self._mode}

    @property
    def min_temp(self):
        """Return the minimum temperature - 4.5 means off."""
        return convert(4.5, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature - 30.5 means on."""
        return convert(30.5, TEMP_CELSIUS, self.unit_of_measurement)

    def update(self):
        """Update the data from the thermostat."""
        try:
            device = ServerProxy(self.address)
            self._current_temperature = device.getValue(
                self._full_device_name,
                PROPERTY_ACTUAL_TEMPERATURE)
            self._target_temperature = device.getValue(
                self._full_device_name,
                PROPERTY_SET_TEMPERATURE)
            self._valve = device.getValue(
                self._full_device_name,
                PROPERTY_VALVE_STATE)
            self._mode = device.getValue(
                self._full_device_name,
                PROPERTY_CONTROL_MODE)

            if self._hm_config.platform_type in [TYPE_HM_THERMOSTAT,
                                                 TYPE_HM_WALLTHERMOSTAT]:
                self._battery = device.getValue(self._maint_device_name,
                                                PROPERTY_BATTERY_STATE)
            elif self._hm_config.platform_type == TYPE_MAX_THERMOSTAT:
                # emulate homematic battery voltage,
                # max reports lowbat if voltage < 2.2V
                # while homematic battery_state should
                # be between 1.5V and 4.6V
                lowbat = device.getValue(self._maint_device_name,
                                         PROPERTY_LOWBAT)
                if lowbat:
                    self._battery = 1.5
                else:
                    self._battery = 4.6

        except Error:
            _LOGGER.exception("Did not receive any temperature data from the "
                              "homematic API.")
