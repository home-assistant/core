"""
The Homematic thermostat platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.homematic/

Important: For this platform to work the homematic component has to be
properly configured.

Configuration:

thermostat:
  - platform: homematic
    address: "<Homematic address for device>" # e.g. "JEQ0XXXXXXX"
    name: "<User defined name>" (optional)
"""

import logging
import homeassistant.components.homematic as homematic
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.helpers.temperature import convert
from homeassistant.const import TEMP_CELSIUS, STATE_UNKNOWN

REQUIREMENTS = ['pyhomematic==0.1.2']

# List of component names (string) your component depends upon.
DEPENDENCIES = ['homematic']

PROPERTY_VALVE_STATE = 'VALVE_STATE'
PROPERTY_CONTROL_MODE = 'CONTROL_MODE'

HMCOMP = 0
MAXCOMP = 1
VARIANTS = {
    "HM-CC-RT-DN": HMCOMP,
    "HM-CC-RT-DN-BoM": HMCOMP,
    "BC-RT-TRX-CyG": MAXCOMP,
    "BC-RT-TRX-CyG-2": MAXCOMP,
    "BC-RT-TRX-CyG-3": MAXCOMP,
    "BC-RT-TRX-CyG-4": MAXCOMP
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_callback_devices, discovery_info=None):
    """Setup the platform."""
    return homematic.setup_hmdevice_entity_helper(HMThermostat,
                                                  config,
                                                  add_callback_devices)


class HMThermostat(homematic.HMDevice, ThermostatDevice):
    """Represents an Homematic Thermostat in Home Assistant."""

    def __init__(self, config):
        """Re-Init the device."""
        super().__init__(config)
        self._battery = STATE_UNKNOWN
        self._rssi = STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._is_connected:
            try:
                return self._current_temperature
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.error("Exception getting current temp.: %s", str(err))
        else:
            return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._is_connected:
            try:
                return self._set_temperature
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.error("Exception getting set temperature: %s",
                              str(err))
        else:
            return None

    def set_temperature(self, temperature):
        """Set new target temperature."""
        if self._is_connected:
            try:
                self._hmdevice.set_temperature = temperature
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.error("Exception setting temperature: %s", str(err))

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        _LOGGER.info("device_state_attributes")
        if self._is_connected:
            return {"valve": self._valve,
                    "battery": self._battery,
                    "mode": self._mode,
                    "rssi": self._rssi}
        else:
            return {"valve": STATE_UNKNOWN,
                    "battery": STATE_UNKNOWN,
                    "mode": STATE_UNKNOWN,
                    "rssi": STATE_UNKNOWN}

    @property
    def min_temp(self):
        """Return the minimum temperature - 4.5 means off."""
        return convert(4.5, TEMP_CELSIUS, self.unit_of_measurement)

    @property
    def max_temp(self):
        """Return the maximum temperature - 30.5 means on."""
        return convert(30.5, TEMP_CELSIUS, self.unit_of_measurement)

    def connect_to_homematic(self):
        """Configuration for device after connection with pyhomematic."""
        def event_received(device, caller, attribute, value):
            """Handler for received events."""
            attribute = str(attribute).upper()
            if attribute == 'SET_TEMPERATURE':
                # pylint: disable=attribute-defined-outside-init
                self._set_temperature = value
            elif attribute == 'ACTUAL_TEMPERATURE':
                # pylint: disable=attribute-defined-outside-init
                self._current_temperature = value
            elif attribute == 'VALVE_STATE':
                # pylint: disable=attribute-defined-outside-init
                self._valve = float(value)
            elif attribute == 'CONTROL_MODE':
                # pylint: disable=attribute-defined-outside-init
                self._mode = value
            elif attribute == 'RSSI_DEVICE':
                self._rssi = value
            elif attribute == 'BATTERY_STATE':
                if isinstance(value, float):
                    self._battery = value
            elif attribute == 'LOWBAT':
                if value:
                    self._battery = 1.5
                else:
                    self._battery = 4.6
            elif attribute == 'UNREACH':
                self._is_available = not bool(value)
            else:
                return
            self.update_ha_state()

        super().connect_to_homematic()
        if self._is_available:
            # pylint: disable=protected-access
            _LOGGER.debug("Setting up thermostat %s", self._hmdevice._ADDRESS)
            try:
                self._hmdevice.setEventCallback(event_received)
                # pylint: disable=attribute-defined-outside-init
                self._current_temperature = self._hmdevice.actual_temperature
                # pylint: disable=attribute-defined-outside-init
                self._set_temperature = self._hmdevice.set_temperature
                self._battery = None
                # pylint: disable=protected-access
                if self._hmdevice._TYPE in VARIANTS:
                    # pylint: disable=protected-access
                    if VARIANTS[self._hmdevice._TYPE] == HMCOMP:
                        self._battery = self._hmdevice.battery_state
                    # pylint: disable=protected-access
                    elif VARIANTS[self._hmdevice._TYPE] == MAXCOMP:
                        if self._hmdevice.battery_state:
                            self._battery = 1.5
                        else:
                            self._battery = 4.6
                # pylint: disable=attribute-defined-outside-init
                self._valve = None
                # pylint: disable=attribute-defined-outside-init
                self._mode = None
                self.update_ha_state()
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.error("Exception while connecting: %s", str(err))
