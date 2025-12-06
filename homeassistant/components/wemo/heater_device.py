"""Representation of a WeMo Heater device."""
from enum import IntEnum
from typing import TypedDict
from pywemo.ouimeaux_device.api.attributes import AttributeDevice


class Mode(IntEnum):
    """Heater operation modes."""
    Off = 0
    Frostprotect = 1
    High = 2
    Low = 3
    Eco = 4


class Temperature(IntEnum):
    """Temperature units."""
    Celsius = 0
    Fahrenheit = 1


class SetTemperature(IntEnum):
    """Target temperature setting."""
    pass


class AutoOffTime(IntEnum):
    """Auto off time in minutes."""
    pass


class TimeRemaining(IntEnum):
    """Time remaining in minutes."""
    pass


class _Attributes(TypedDict, total=False):
    """Attributes for the WeMo Heater."""
    Mode: int
    Temperature: float
    SetTemperature: float
    AutoOffTime: int
    RunMode: int
    TimeRemaining: int
    WemoDisabled: int
    TempUnit: int


class Heater(AttributeDevice):
    """Representation of a WeMo Heater device."""
    _state_property = "mode"
    _attributes: _Attributes

    def __repr__(self):
        """Return a string representation of the device."""
        return f'<WeMo Heater "{self.name}">'

    @property
    def mode(self):
        """Return the current heater mode."""
        return Mode(self._attributes.get('Mode', 0))

    @property
    def mode_string(self):
        """Return the current mode as a string."""
        return self.mode.name

    def set_mode(self, mode):
        """Set the heater mode."""
        if isinstance(mode, str):
            mode = Mode[mode]
        self._set_attributes(('Mode', int(mode)))

    @property
    def current_temperature(self):
        """Return the current temperature in current units.
        
        Note: Device returns temperature in the display unit (respects TempUnit setting).
        """
        return float(self._attributes.get('Temperature', 0))

    @property
    def target_temperature(self):
        """Return the target temperature in current units.
        
        Note: Device returns temperature in the display unit (respects TempUnit setting).
        """
        return float(self._attributes.get('SetTemperature', 0))

    def set_target_temperature(self, temperature):
        """Set the target temperature.
        
        Args:
            temperature: Target temperature in current display unit (Celsius or Fahrenheit
                        based on temperature_unit property)
        
        Notes:
            CRITICAL: The WeMo heater API has an asymmetric behavior:
            - INPUT (SetAttributes): Always expects Fahrenheit regardless of TempUnit
            - OUTPUT (GetAttributes): Returns temperature in current display unit
            
            This method automatically converts Celsius to Fahrenheit when sending
            to the device API, ensuring proper temperature setting in Celsius mode.
        """
        # Round to nearest whole degree
        temp_value = float(round(temperature))
        
        # CRITICAL FIX: Convert to Fahrenheit if currently in Celsius mode
        # The device API always expects Fahrenheit for input!
        if self.temperature_unit == Temperature.Celsius:
            # Convert Celsius to Fahrenheit for API
            temp_fahrenheit = (temp_value * 9.0 / 5.0) + 32.0
        else:
            # Already in Fahrenheit
            temp_fahrenheit = temp_value
        
        # Send Fahrenheit to device (API requirement)
        self._set_attributes(('SetTemperature', temp_fahrenheit))
        
        # DON'T cache here - let climate.py handle caching
        # The device will return the correct value on next refresh

    @property
    def temperature_unit(self):
        """Return the temperature unit (0=C, 1=F)."""
        return Temperature(self._attributes.get('TempUnit', 0))

    @property
    def temperature_unit_string(self):
        """Return temperature unit as string."""
        return "C" if self.temperature_unit == Temperature.Celsius else "F"

    def set_temperature_unit(self, unit):
        """Set the temperature unit.
        
        Note: This only changes the DISPLAY unit. The API still expects
        Fahrenheit for input (handled automatically by set_target_temperature).
        """
        if isinstance(unit, str):
            unit = Temperature.Celsius if unit.upper() == 'C' else Temperature.Fahrenheit
        self._set_attributes(('TempUnit', int(unit)))

    @property
    def auto_off_time(self):
        """Return the auto off time in minutes."""
        return int(self._attributes.get('AutoOffTime', 0))

    def set_auto_off_time(self, minutes):
        """Set auto off time in minutes."""
        self._set_attributes(('AutoOffTime', int(minutes)))

    @property
    def time_remaining(self):
        """Return time remaining in minutes before auto off."""
        return int(self._attributes.get('TimeRemaining', 0))

    @property
    def heating_status(self):
        """Return whether the heater is actively heating."""
        return self.mode != Mode.Off

    def turn_on(self):
        """Turn the heater on to Eco mode."""
        self.set_mode(Mode.Eco)

    def turn_off(self):
        """Turn the heater off."""
        self.set_mode(Mode.Off)

    @property
    def state(self):
        """Return 1 if heater is on (not in Off mode), 0 otherwise."""
        return 0 if self.mode == Mode.Off else 1

    def get_state(self, force_update=False):
        """Return the state of the device."""
        if force_update:
            self.update_attributes()
        return self.state

    def get_temperature_range(self):
        """Return the valid temperature range for this device.
        
        Returns:
            tuple: (min_temp, max_temp) in current display unit
        
        Note:
            These are typical ranges for WeMo heaters.
        """
        if self.temperature_unit == Temperature.Celsius:
            return (16, 29)  # Typical Celsius range
        else:
            return (60, 85)  # Typical Fahrenheit range
