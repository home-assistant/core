"""
Demo platform that offers a fake hvac.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.hvac import HvacDevice
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo hvacs."""
    add_devices([
        DemoHvac("HeatPump", 68, TEMP_FAHRENHEIT, None, 77, "Auto Low",
                 None, None, "Auto", "Heat", None),
        DemoHvac("Hvac", 21, TEMP_CELSIUS, True, 22, "On High",
                 67, 54, "Off", "Cool", False),
    ])


# pylint: disable=too-many-arguments, too-many-public-methods
class DemoHvac(HvacDevice):
    """Representation of a demo hvac."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, target_temperature, unit_of_measurement,
                 away, current_temperature, current_fan_mode,
                 target_humidity, current_humidity, current_swing_mode,
                 current_operation, aux):
        """Initialize the hvac."""
        self._name = name
        self._target_temperature = target_temperature
        self._target_humidity = target_humidity
        self._unit_of_measurement = unit_of_measurement
        self._away = away
        self._current_temperature = current_temperature
        self._current_humidity = current_humidity
        self._current_fan_mode = current_fan_mode
        self._current_operation = current_operation
        self._aux = aux
        self._current_swing_mode = current_swing_mode
        self._fan_list = ["On Low", "On High", "Auto Low", "Auto High", "Off"]
        self._operation_list = ["Heat", "Cool", "Auto Changeover", "Off"]
        self._swing_list = ["Auto", 1, 2, 3, "Off"]

    @property
    def should_poll(self):
        """Polling not needed for a demo hvac."""
        return False

    @property
    def name(self):
        """Return the name of the hvac."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
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
    def is_aux_heat_on(self):
        """Return true if away mode is on."""
        return self._aux

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def set_temperature(self, temperature):
        """Set new target temperature."""
        self._target_temperature = temperature
        self.update_ha_state()

    def set_humidity(self, humidity):
        """Set new target temperature."""
        self._target_humidity = humidity
        self.update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self._current_swing_mode = swing_mode
        self.update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        self._current_fan_mode = fan
        self.update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self._current_operation = operation_mode
        self.update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.update_ha_state()

    def turn_aux_heat_on(self):
        """Turn away auxillary heater on."""
        self._aux = True
        self.update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        self._aux = False
        self.update_ha_state()
