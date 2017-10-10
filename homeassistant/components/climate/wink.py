"""
Support for Wink thermostats, Air Conditioners, and Water Heaters.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.wink/
"""
import logging
import asyncio

from homeassistant.components.wink import WinkDevice, DOMAIN
from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, ClimateDevice,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE, STATE_FAN_ONLY,
    ATTR_CURRENT_HUMIDITY, STATE_ECO, STATE_ELECTRIC,
    STATE_PERFORMANCE, STATE_HIGH_DEMAND,
    STATE_HEAT_PUMP, STATE_GAS)
from homeassistant.const import (
    TEMP_CELSIUS, STATE_ON,
    STATE_OFF, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['wink']

SPEED_LOW = 'low'
SPEED_MEDIUM = 'medium'
SPEED_HIGH = 'high'

HA_STATE_TO_WINK = {STATE_AUTO: 'auto',
                    STATE_ECO: 'eco',
                    STATE_FAN_ONLY: 'fan_only',
                    STATE_HEAT: 'heat_only',
                    STATE_COOL: 'cool_only',
                    STATE_PERFORMANCE: 'performance',
                    STATE_HIGH_DEMAND: 'high_demand',
                    STATE_HEAT_PUMP: 'heat_pump',
                    STATE_ELECTRIC: 'electric_only',
                    STATE_GAS: 'gas',
                    STATE_OFF: 'off'}
WINK_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_WINK.items()}

ATTR_EXTERNAL_TEMPERATURE = "external_temperature"
ATTR_SMART_TEMPERATURE = "smart_temperature"
ATTR_ECO_TARGET = "eco_target"
ATTR_OCCUPIED = "occupied"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Wink climate devices."""
    import pywink
    for climate in pywink.get_thermostats():
        _id = climate.object_id() + climate.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkThermostat(climate, hass)])
    for climate in pywink.get_air_conditioners():
        _id = climate.object_id() + climate.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkAC(climate, hass)])
    for water_heater in pywink.get_water_heaters():
        _id = water_heater.object_id() + water_heater.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_devices([WinkWaterHeater(water_heater, hass)])


# pylint: disable=abstract-method
class WinkThermostat(WinkDevice, ClimateDevice):
    """Representation of a Wink thermostat."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['climate'].append(self)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        # The Wink API always returns temp in Celsius
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        data = {}
        target_temp_high = self.target_temperature_high
        target_temp_low = self.target_temperature_low
        if target_temp_high is not None:
            data[ATTR_TARGET_TEMP_HIGH] = self._convert_for_display(
                self.target_temperature_high)
        if target_temp_low is not None:
            data[ATTR_TARGET_TEMP_LOW] = self._convert_for_display(
                self.target_temperature_low)

        if self.external_temperature:
            data[ATTR_EXTERNAL_TEMPERATURE] = self._convert_for_display(
                self.external_temperature)

        if self.smart_temperature:
            data[ATTR_SMART_TEMPERATURE] = self.smart_temperature

        if self.occupied:
            data[ATTR_OCCUPIED] = self.occupied

        if self.eco_target:
            data[ATTR_ECO_TARGET] = self.eco_target

        current_humidity = self.current_humidity
        if current_humidity is not None:
            data[ATTR_CURRENT_HUMIDITY] = current_humidity

        return data

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.wink.current_temperature()

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if self.wink.current_humidity() is not None:
            # The API states humidity will be a float 0-1
            # the only example API response with humidity listed show an int
            # This will address both possibilities
            if self.wink.current_humidity() < 1:
                return self.wink.current_humidity() * 100
            return self.wink.current_humidity()
        return None

    @property
    def external_temperature(self):
        """Return the current external temperature."""
        return self.wink.current_external_temperature()

    @property
    def smart_temperature(self):
        """Return the current average temp of all remote sensor."""
        return self.wink.current_smart_temperature()

    @property
    def eco_target(self):
        """Return status of eco target (Is the termostat in eco mode)."""
        return self.wink.eco_target()

    @property
    def occupied(self):
        """Return status of if the thermostat has detected occupancy."""
        return self.wink.occupied()

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if not self.wink.is_on():
            current_op = STATE_OFF
        else:
            current_op = WINK_STATE_TO_HA.get(self.wink.current_hvac_mode())
            if current_op == 'aux':
                return STATE_HEAT
            if current_op is None:
                current_op = STATE_UNKNOWN
        return current_op

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        target_hum = None
        if self.wink.current_humidifier_mode() == 'on':
            if self.wink.current_humidifier_set_point() is not None:
                target_hum = self.wink.current_humidifier_set_point() * 100
        elif self.wink.current_dehumidifier_mode() == 'on':
            if self.wink.current_dehumidifier_set_point() is not None:
                target_hum = self.wink.current_dehumidifier_set_point() * 100
        else:
            target_hum = None
        return target_hum

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.current_operation != STATE_AUTO and not self.is_away_mode_on:
            if self.current_operation == STATE_COOL:
                return self.wink.current_max_set_point()
            elif self.current_operation == STATE_HEAT:
                return self.wink.current_min_set_point()
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return self.wink.current_min_set_point()
        return None

    @property
    def target_temperature_high(self):
        """Return the higher bound temperature we try to reach."""
        if self.current_operation == STATE_AUTO:
            return self.wink.current_max_set_point()
        return None

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self.wink.away()

    @property
    def is_aux_heat_on(self):
        """Return true if aux heater."""
        if 'aux' not in self.wink.hvac_modes():
            return None

        if self.wink.current_hvac_mode() == 'aux':
            return True
        return False

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp is not None:
            if self.current_operation == STATE_COOL:
                target_temp_high = target_temp
            if self.current_operation == STATE_HEAT:
                target_temp_low = target_temp
        if target_temp_low is not None:
            target_temp_low = target_temp_low
        if target_temp_high is not None:
            target_temp_high = target_temp_high
        self.wink.set_temperature(target_temp_low, target_temp_high)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        op_mode_to_set = HA_STATE_TO_WINK.get(operation_mode)
        # The only way to disable aux heat is with the toggle
        if self.is_aux_heat_on and op_mode_to_set == STATE_HEAT:
            return
        self.wink.set_operation_mode(op_mode_to_set)

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = ['off']
        modes = self.wink.hvac_modes()
        for mode in modes:
            if mode == 'aux':
                continue
            ha_mode = WINK_STATE_TO_HA.get(mode)
            if ha_mode is not None:
                op_list.append(ha_mode)
            else:
                error = "Invaid operation mode mapping. " + mode + \
                    " doesn't map. Please report this."
                _LOGGER.error(error)
        return op_list

    def turn_away_mode_on(self):
        """Turn away on."""
        self.wink.set_away_mode()

    def turn_away_mode_off(self):
        """Turn away off."""
        self.wink.set_away_mode(False)

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        if self.wink.current_fan_mode() == 'on':
            return STATE_ON
        elif self.wink.current_fan_mode() == 'auto':
            return STATE_AUTO
        # No Fan available so disable slider
        return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        if self.wink.has_fan():
            return self.wink.fan_modes()
        return None

    def set_fan_mode(self, fan):
        """Turn fan on/off."""
        self.wink.set_fan_mode(fan.lower())

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self.wink.set_operation_mode('aux')

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self.set_operation_mode(STATE_HEAT)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        minimum = 7  # Default minimum
        min_min = self.wink.min_min_set_point()
        min_max = self.wink.min_max_set_point()
        return_value = minimum
        if self.current_operation == STATE_HEAT:
            if min_min:
                return_value = min_min
            else:
                return_value = minimum
        elif self.current_operation == STATE_COOL:
            if min_max:
                return_value = min_max
            else:
                return_value = minimum
        elif self.current_operation == STATE_AUTO:
            if min_min and min_max:
                return_value = min(min_min, min_max)
            else:
                return_value = minimum
        else:
            return_value = minimum
        return return_value

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        maximum = 35  # Default maximum
        max_min = self.wink.max_min_set_point()
        max_max = self.wink.max_max_set_point()
        return_value = maximum
        if self.current_operation == STATE_HEAT:
            if max_min:
                return_value = max_min
            else:
                return_value = maximum
        elif self.current_operation == STATE_COOL:
            if max_max:
                return_value = max_max
            else:
                return_value = maximum
        elif self.current_operation == STATE_AUTO:
            if max_min and max_max:
                return_value = min(max_min, max_max)
            else:
                return_value = maximum
        else:
            return_value = maximum
        return return_value


class WinkAC(WinkDevice, ClimateDevice):
    """Representation of a Wink air conditioner."""

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        # The Wink API always returns temp in Celsius
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        data = {}
        target_temp_high = self.target_temperature_high
        target_temp_low = self.target_temperature_low
        if target_temp_high is not None:
            data[ATTR_TARGET_TEMP_HIGH] = self._convert_for_display(
                self.target_temperature_high)
        if target_temp_low is not None:
            data[ATTR_TARGET_TEMP_LOW] = self._convert_for_display(
                self.target_temperature_low)
        data["total_consumption"] = self.wink.total_consumption()
        data["schedule_enabled"] = self.wink.schedule_enabled()

        return data

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.wink.current_temperature()

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if not self.wink.is_on():
            current_op = STATE_OFF
        else:
            current_op = WINK_STATE_TO_HA.get(self.wink.current_hvac_mode())
            if current_op is None:
                current_op = STATE_UNKNOWN
        return current_op

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = ['off']
        modes = self.wink.modes()
        for mode in modes:
            ha_mode = WINK_STATE_TO_HA.get(mode)
            if ha_mode is not None:
                op_list.append(ha_mode)
            else:
                error = "Invaid operation mode mapping. " + mode + \
                    " doesn't map. Please report this."
                _LOGGER.error(error)
        return op_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        self.wink.set_temperature(target_temp)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        op_mode_to_set = HA_STATE_TO_WINK.get(operation_mode)
        if op_mode_to_set == 'eco':
            op_mode_to_set = 'auto_eco'
        self.wink.set_operation_mode(op_mode_to_set)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.wink.current_max_set_point()

    @property
    def current_fan_mode(self):
        """Return the current fan mode."""
        speed = self.wink.current_fan_speed()
        if speed <= 0.4 and speed > 0.3:
            return SPEED_LOW
        elif speed <= 0.8 and speed > 0.5:
            return SPEED_MEDIUM
        elif speed <= 1.0 and speed > 0.8:
            return SPEED_HIGH
        return STATE_UNKNOWN

    @property
    def fan_list(self):
        """Return a list of available fan modes."""
        return [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def set_fan_mode(self, fan):
        """Set fan speed."""
        if fan == SPEED_LOW:
            speed = 0.4
        elif fan == SPEED_MEDIUM:
            speed = 0.8
        elif fan == SPEED_HIGH:
            speed = 1.0
        self.wink.set_ac_fan_speed(speed)


class WinkWaterHeater(WinkDevice, ClimateDevice):
    """Representation of a Wink water heater."""

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        # The Wink API always returns temp in Celsius
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        data = {}
        data["vacation_mode"] = self.wink.vacation_mode_enabled()
        data["rheem_type"] = self.wink.rheem_type()

        return data

    @property
    def current_operation(self):
        """
        Return current operation one of the following.

        ["eco", "performance", "heat_pump",
        "high_demand", "electric_only", "gas]
        """
        if not self.wink.is_on():
            current_op = STATE_OFF
        else:
            current_op = WINK_STATE_TO_HA.get(self.wink.current_mode())
            if current_op is None:
                current_op = STATE_UNKNOWN
        return current_op

    @property
    def operation_list(self):
        """List of available operation modes."""
        op_list = ['off']
        modes = self.wink.modes()
        for mode in modes:
            if mode == 'aux':
                continue
            ha_mode = WINK_STATE_TO_HA.get(mode)
            if ha_mode is not None:
                op_list.append(ha_mode)
            else:
                error = "Invaid operation mode mapping. " + mode + \
                    " doesn't map. Please report this."
                _LOGGER.error(error)
        return op_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        self.wink.set_temperature(target_temp)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        op_mode_to_set = HA_STATE_TO_WINK.get(operation_mode)
        self.wink.set_operation_mode(op_mode_to_set)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.wink.current_set_point()

    def turn_away_mode_on(self):
        """Turn away on."""
        self.wink.set_vacation_mode(True)

    def turn_away_mode_off(self):
        """Turn away off."""
        self.wink.set_vacation_mode(False)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.wink.min_set_point()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.wink.max_set_point()
