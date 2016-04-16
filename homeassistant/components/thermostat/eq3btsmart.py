"""
Support for eq3 Bluetooth Smart thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.max/
"""
import logging
import struct
from datetime import datetime

from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.temperature import convert

REQUIREMENTS = ['bluepy>=1.0.0']

CONF_MAC = 'mac'
CONF_DEVICES = 'devices'
CONF_ID = 'id'

PROP_WRITE_HANDLE = 0x411
PROP_NTFY_HANDLE = 0x421
PROP_ID_VALUE_PACKED = struct.pack('B', 0)
PROP_GETINFO_VALUE_PACKED = struct.pack('B', 3)
PROP_TEMPERATURE_VALUE = 0x41
PROP_TEMPERATURE_VALUE_PACKED = struct.pack(
    'B', PROP_TEMPERATURE_VALUE)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the eq3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        devices.append(EQ3BTSmartThermostat(mac, name))

    add_devices(devices)
    return True


# pylint: disable=too-many-instance-attributes
class EQ3BTSmartThermostat(ThermostatDevice):
    """Representation of a Homematic thermostat."""

    def __init__(self, _mac, _name):
        """Initialize the thermostat."""
        from bluepy import btle

        self._mac = _mac
        self._name = _name
        self._target_temperature = -1
        self._mode = -1
        self._mode_readable = ''
        self._request_value = -1
        self._request_handle = -1

        self._conn = btle.Peripheral()
        self._connect()
        self.update()

    def get_delegate(self):
        """Return the notification handler."""
        from bluepy import btle

        class EQ3BTSmartDelegate(btle.DefaultDelegate):
            """Class for Callback handling."""

            def __init__(self, _thermostat):
                """Initialize the Callback handler."""
                btle.DefaultDelegate.__init__(self)
                self._thermostat = _thermostat

            def handleNotification(self, handle, data):
                """Handle Callback from a Bluetooth (GATT) request."""
                self._thermostat.handle_notification(handle, data)

        return EQ3BTSmartDelegate(self)

    def handle_notification(self, handle, data):
        """Handle Callback from a Bluetooth (GATT) request."""
        if handle == PROP_NTFY_HANDLE:
            if self._request_value == PROP_GETINFO_VALUE_PACKED:
                self._mode = data[2] & 1
                self._mode_readable = self.decode_mode(data[2])
                self._target_temperature = data[5] / 2.0

    def _connect(self):
        """Connect to the Bluetooth thermostat."""
        _LOGGER.info("EQ3 Smart BLE: connecting to " + self._name +
                     " " + self._mac)
        self._conn.connect(self._mac)
        delegate = self.get_delegate()
        self._conn.withDelegate(delegate)
        self._set_time()

    def _set_time(self):
        """Set the correct time into the thermostat."""
        time = datetime.now()
        value = struct.pack('BBBBBB', int(time.strftime("%y")),
                            time.month, time.day, time.hour,
                            time.minute, time.second)
        self.write_command_raw(PROP_WRITE_HANDLE, value)

    def _disconnect(self):
        """Close the Bluetooth connection."""
        self._conn.disconnect()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELCIUS

    @property
    def current_temperature(self):
        """Can not report temperature, so return target_temperature."""
        return self.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, temperature):
        """Set new target temperature."""
        value = struct.pack('BB', PROP_TEMPERATURE_VALUE,
                            int(temperature*2))
        self.write_request_raw(PROP_WRITE_HANDLE, value)
        self._target_temperature = temperature

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {"mode": self._mode, "mode_readable": self._mode_readable}

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return round(convert(4.5, TEMP_CELCIUS, self.unit_of_measurement))

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return round(convert(30.5, TEMP_CELCIUS, self.unit_of_measurement))

    @staticmethod
    def decode_mode(mode):
        """Convert the numerical mode to a human-readable description."""
        ret = ""
        if mode & 1:
            ret = "manual"
        else:
            ret = "auto"

        if mode & 2:
            ret = ret + " holiday"
        if mode & 4:
            ret = ret + " boost"
        if mode & 8:
            ret = ret + " dst"
        if mode & 16:
            ret = ret + " window"

        return ret

    def write_request(self, handle, value):
        """Write a GATT Command with callback."""
        self.write_command(handle, value, True)

    def write_request_raw(self, handle, value):
        """Write a GATT Command with callback - no utf-8."""
        self.write_command_raw(handle, value, True)

    def write_command(self, handle, value, wait_for_it=False):
        """Write a GATT Command without callback."""
        self.write_command(handle, value.encode('utf-8'), wait_for_it)

    def write_command_raw(self, handle, value,
                          wait_for_it=False, exception=False):
        """Write a GATT Command without callback - not utf-8."""
        from bluepy import btle

        try:
            self._request_handle = handle
            self._request_value = value
            self._conn.writeCharacteristic(handle, value, wait_for_it)
            if wait_for_it:
                while self._conn.waitForNotifications(1):
                    continue
        except btle.BTLEException:
            if exception is False:
                self._disconnect()
                self._connect()
                self.write_command_raw(handle, value, wait_for_it, True)

    def update(self):
        """Update the data from the thermostat."""
        self.write_request_raw(PROP_WRITE_HANDLE,
                               PROP_GETINFO_VALUE_PACKED)
