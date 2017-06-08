"""
Demo platform that offers fake boiler controllers.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.boiler import (
    BoilerDevice, ATTR_TARGET_WATER_TEMPERATURE, ATTR_PANEL_DIFF_TEMP)
from homeassistant.const import TEMP_CELSIUS  # TEMP_FAHRENHEIT


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo boiler controller."""
    add_devices([
        DemoBoiler("GeyserWise", "electric", 55, None, TEMP_CELSIUS,
                   False, False, False, "heat", False),
        DemoBoiler("GeyserWise Max", "pumped solar", 65, 7, TEMP_CELSIUS,
                   False, False, False, "pump", False),
        DemoBoiler("QwikSwitch", "electric", 60, None, TEMP_CELSIUS,
                   False, False, False, "idle", False)
    ])

    return True


# pylint: disable=too-many-arguments, too-many-public-methods
class DemoBoiler(BoilerDevice):
    """Representation of a demo boiler."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, boiler_type,
                 target_water_temperature, panel_differential_temp,
                 unit_of_measurement, away, guest, holiday, current_operation,
                 boost):
        """Initialize the boiler controller."""
        self._name = name
        self._boiler_type = boiler_type
        self._target_water_temperature = target_water_temperature
        self._panel_differential_temp = panel_differential_temp
        self._unit_of_measurement = unit_of_measurement
        self._away = away
        self._guest = guest
        self._total_guests = 0  # Will never be initialised with non-zero
        self._holiday = holiday
        self._holiday_duration = 0  # Will never be initialised with non-zero
        self._current_operation = current_operation
        self._boost = boost
        self._current_water_temperature = None
        self._current_element_status = None
        self._current_pump_mode = None
        self._fault_code = None  # Cannot be initialised with a fault code
        self._operation_list = ["cool",   # Prevent overheating
                                "error",  # Boiler needs attention
                                "frost",  # Prevent freezing of collector
                                "heat",   # Heating water
                                "idle",   # Water on temp
                                "kill",   # Heat above 60 for Legionella
                                "off"]    # Only applicable to normal units

    @property
    def should_poll(self):
        """Polling not needed for a demo boiler."""
        return False

    @property
    def name(self):
        """Return the name of the boiler."""
        return self._name

    @property
    def boiler_class(self):
        """Return the unit of measurement."""
        return self._boiler_type

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_water_temperature(self):
        """Return the current temperature."""
        return self._current_water_temperature

    @property
    def target_water_temperature(self):
        """Return the temperature to keep."""
        return self._target_water_temperature

    @property
    def panel_differential_temperature(self):
        """Return the differential temperature to start pumping at."""
        return self._panel_differential_temp

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, defrost."""
        return self._current_operation

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def is_guest_mode_on(self):
        """Return if guest mode is on."""
        return self._guest

    @property
    def total_guests(self):
        """Return the total number of guests."""
        return self._total_guests

    @property
    def is_holiday_mode_on(self):
        """Return if holiday mode is on."""
        return self._holiday

    @property
    def holiday_duration(self):
        """Return the duration of the holiday, in days."""
        return self._holiday_duration

    @property
    def is_element_on(self):
        """Return the element setting."""
        return self._current_element_status

    @property
    def is_pump_on(self):
        """Return the pump setting."""
        return self._current_pump_mode

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        # Ideally this should be a self learning formula,
        # based on crowd sourced data and taking many variables into account
        # But let start with based on user preference ;-)
        self._target_water_temperature = kwargs.get(
            ATTR_TARGET_WATER_TEMPERATURE)
        if kwargs.get(ATTR_PANEL_DIFF_TEMP) is not None:
            self._panel_differential_temp = kwargs.get(ATTR_PANEL_DIFF_TEMP)
        self.update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self._current_operation = operation_mode
        self.update_ha_state()

    def turn_element_on(self):
        """Turn element on."""
        self._current_element_status = True
        self.update_ha_state()

    def turn_element_off(self):
        """Turn element off."""
        self._current_element_status = False
        self.update_ha_state()

    def turn_pump_on(self):
        """Turn pump on."""
        self._current_pump_mode = True
        self.update_ha_state()

    def turn_pump_off(self):
        """Turn pump off."""
        self._current_pump_mode = False
        self.update_ha_state()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.update_ha_state()

    def turn_guest_mode_on(self, total_guests):
        """Turn guest mode on."""
        # We need a formula that set the target temp based on
        # number of people, boiler volume, element rating, weather, etc.
        self._guest = True
        self._total_guests = total_guests
        self.update_ha_state()

    def turn_guest_mode_off(self):
        """Turn guest mode off."""
        self._guest = False
        self._total_guests = 0
        self.update_ha_state()

    def turn_holiday_mode_on(self, holiday_duration):
        """Turn holiday mode on."""
        # We need a formula that set the target temp based on
        # number of days away, boiler volume, element rating, weather, etc.
        self._holiday = True
        self._holiday_duration = holiday_duration
        self.update_ha_state()

    def turn_holiday_mode_off(self):
        """Turn holiday mode off."""
        self._away = False
        self._holiday_duration = 0
        self.update_ha_state()
