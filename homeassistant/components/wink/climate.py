"""Support for Wink thermostats and Air Conditioners."""
import logging

import pywink

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.helpers.temperature import display_temp as show_temp

from . import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

ATTR_ECO_TARGET = "eco_target"
ATTR_EXTERNAL_TEMPERATURE = "external_temperature"
ATTR_OCCUPIED = "occupied"
ATTR_SCHEDULE_ENABLED = "schedule_enabled"
ATTR_SMART_TEMPERATURE = "smart_temperature"
ATTR_TOTAL_CONSUMPTION = "total_consumption"

HA_HVAC_TO_WINK = {
    HVAC_MODE_AUTO: "auto",
    HVAC_MODE_COOL: "cool_only",
    HVAC_MODE_FAN_ONLY: "fan_only",
    HVAC_MODE_HEAT: "heat_only",
    HVAC_MODE_OFF: "off",
}

WINK_HVAC_TO_HA = {value: key for key, value in HA_HVAC_TO_WINK.items()}

SUPPORT_FLAGS_THERMOSTAT = (
    SUPPORT_TARGET_TEMPERATURE
    | SUPPORT_TARGET_TEMPERATURE_RANGE
    | SUPPORT_FAN_MODE
    | SUPPORT_AUX_HEAT
)
SUPPORT_FAN_THERMOSTAT = [FAN_AUTO, FAN_ON]
SUPPORT_PRESET_THERMOSTAT = [PRESET_AWAY, PRESET_ECO]

SUPPORT_FLAGS_AC = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE
SUPPORT_FAN_AC = [FAN_HIGH, FAN_LOW, FAN_MEDIUM]
SUPPORT_PRESET_AC = [PRESET_NONE, PRESET_ECO]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink climate devices."""
    for climate in pywink.get_thermostats():
        _id = climate.object_id() + climate.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkThermostat(climate, hass)])
    for climate in pywink.get_air_conditioners():
        _id = climate.object_id() + climate.name()
        if _id not in hass.data[DOMAIN]["unique_ids"]:
            add_entities([WinkAC(climate, hass)])


class WinkThermostat(WinkDevice, ClimateEntity):
    """Representation of a Wink thermostat."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_THERMOSTAT

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]["entities"]["climate"].append(self)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        # The Wink API always returns temp in Celsius
        return TEMP_CELSIUS

    @property
    def extra_state_attributes(self):
        """Return the optional device state attributes."""
        data = {}
        if self.external_temperature is not None:
            data[ATTR_EXTERNAL_TEMPERATURE] = show_temp(
                self.hass,
                self.external_temperature,
                self.temperature_unit,
                PRECISION_TENTHS,
            )

        if self.smart_temperature:
            data[ATTR_SMART_TEMPERATURE] = self.smart_temperature

        if self.occupied is not None:
            data[ATTR_OCCUPIED] = self.occupied

        if self.eco_target is not None:
            data[ATTR_ECO_TARGET] = self.eco_target

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
        """Return status of eco target (Is the thermostat in eco mode)."""
        return self.wink.eco_target()

    @property
    def occupied(self):
        """Return status of if the thermostat has detected occupancy."""
        return self.wink.occupied()

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        mode = self.wink.current_hvac_mode()
        if mode == "eco":
            return PRESET_ECO
        if self.wink.away():
            return PRESET_AWAY
        return None

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET_THERMOSTAT

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        target_hum = None
        if self.wink.current_humidifier_mode() == "on":
            if self.wink.current_humidifier_set_point() is not None:
                target_hum = self.wink.current_humidifier_set_point() * 100
        elif self.wink.current_dehumidifier_mode() == "on":
            if self.wink.current_dehumidifier_set_point() is not None:
                target_hum = self.wink.current_dehumidifier_set_point() * 100
        else:
            target_hum = None
        return target_hum

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode != HVAC_MODE_AUTO and not self.wink.away():
            if self.hvac_mode == HVAC_MODE_COOL:
                return self.wink.current_max_set_point()
            if self.hvac_mode == HVAC_MODE_HEAT:
                return self.wink.current_min_set_point()
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return self.wink.current_min_set_point()
        return None

    @property
    def target_temperature_high(self):
        """Return the higher bound temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_AUTO:
            return self.wink.current_max_set_point()
        return None

    @property
    def is_aux_heat(self):
        """Return true if aux heater."""
        if "aux" not in self.wink.hvac_modes():
            return None
        if self.wink.current_hvac_mode() == "aux":
            return True
        return False

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if not self.wink.is_on():
            return HVAC_MODE_OFF

        wink_mode = self.wink.current_hvac_mode()
        if wink_mode == "aux":
            return HVAC_MODE_HEAT
        if wink_mode == "eco":
            return HVAC_MODE_AUTO
        return WINK_HVAC_TO_HA.get(wink_mode)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        hvac_list = [HVAC_MODE_OFF]

        modes = self.wink.hvac_modes()
        for mode in modes:
            if mode in ("eco", "aux"):
                continue
            try:
                ha_mode = WINK_HVAC_TO_HA[mode]
                hvac_list.append(ha_mode)
            except KeyError:
                _LOGGER.error(
                    "Invalid operation mode mapping. %s doesn't map. "
                    "Please report this",
                    mode,
                )
        return hvac_list

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if not self.wink.is_on():
            return CURRENT_HVAC_OFF
        if self.wink.cool_on():
            return CURRENT_HVAC_COOL
        if self.wink.heat_on():
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp is not None:
            if self.hvac_mode == HVAC_MODE_COOL:
                target_temp_high = target_temp
            if self.hvac_mode == HVAC_MODE_HEAT:
                target_temp_low = target_temp
        self.wink.set_temperature(target_temp_low, target_temp_high)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        hvac_mode_to_set = HA_HVAC_TO_WINK.get(hvac_mode)
        self.wink.set_operation_mode(hvac_mode_to_set)

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        # Away
        if preset_mode != PRESET_AWAY and self.wink.away():
            self.wink.set_away_mode(False)
        elif preset_mode == PRESET_AWAY:
            self.wink.set_away_mode()

        if preset_mode == PRESET_ECO:
            self.wink.set_operation_mode("eco")

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        if self.wink.current_fan_mode() == "on":
            return FAN_ON
        if self.wink.current_fan_mode() == "auto":
            return FAN_AUTO
        # No Fan available so disable slider
        return None

    @property
    def fan_modes(self):
        """List of available fan modes."""
        if self.wink.has_fan():
            return SUPPORT_FAN_THERMOSTAT
        return None

    def set_fan_mode(self, fan_mode):
        """Turn fan on/off."""
        self.wink.set_fan_mode(fan_mode.lower())

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self.wink.set_operation_mode("aux")

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self.wink.set_operation_mode("heat_only")

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        minimum = 7  # Default minimum
        min_min = self.wink.min_min_set_point()
        min_max = self.wink.min_max_set_point()
        if self.hvac_mode == HVAC_MODE_HEAT:
            if min_min:
                return_value = min_min
            else:
                return_value = minimum
        elif self.hvac_mode == HVAC_MODE_COOL:
            if min_max:
                return_value = min_max
            else:
                return_value = minimum
        elif self.hvac_mode == HVAC_MODE_AUTO:
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
        if self.hvac_mode == HVAC_MODE_HEAT:
            if max_min:
                return_value = max_min
            else:
                return_value = maximum
        elif self.hvac_mode == HVAC_MODE_COOL:
            if max_max:
                return_value = max_max
            else:
                return_value = maximum
        elif self.hvac_mode == HVAC_MODE_AUTO:
            if max_min and max_max:
                return_value = min(max_min, max_max)
            else:
                return_value = maximum
        else:
            return_value = maximum
        return return_value


class WinkAC(WinkDevice, ClimateEntity):
    """Representation of a Wink air conditioner."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS_AC

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        # The Wink API always returns temp in Celsius
        return TEMP_CELSIUS

    @property
    def extra_state_attributes(self):
        """Return the optional device state attributes."""
        data = {}
        data[ATTR_TOTAL_CONSUMPTION] = self.wink.total_consumption()
        data[ATTR_SCHEDULE_ENABLED] = self.wink.schedule_enabled()

        return data

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.wink.current_temperature()

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if not self.wink.is_on():
            return PRESET_NONE

        mode = self.wink.current_mode()
        if mode == "auto_eco":
            return PRESET_ECO
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET_AC

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if not self.wink.is_on():
            return HVAC_MODE_OFF

        wink_mode = self.wink.current_mode()
        if wink_mode == "auto_eco":
            return HVAC_MODE_COOL
        return WINK_HVAC_TO_HA.get(wink_mode)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        hvac_list = [HVAC_MODE_OFF]

        modes = self.wink.modes()
        for mode in modes:
            if mode == "auto_eco":
                continue
            try:
                ha_mode = WINK_HVAC_TO_HA[mode]
                hvac_list.append(ha_mode)
            except KeyError:
                _LOGGER.error(
                    "Invalid operation mode mapping. %s doesn't map. "
                    "Please report this",
                    mode,
                )
        return hvac_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        self.wink.set_temperature(target_temp)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        hvac_mode_to_set = HA_HVAC_TO_WINK.get(hvac_mode)
        self.wink.set_operation_mode(hvac_mode_to_set)

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_ECO:
            self.wink.set_operation_mode("auto_eco")
        elif self.hvac_mode == HVAC_MODE_COOL and preset_mode == PRESET_NONE:
            self.set_hvac_mode(HVAC_MODE_COOL)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.wink.current_max_set_point()

    @property
    def fan_mode(self):
        """
        Return the current fan mode.

        The official Wink app only supports 3 modes [low, medium, high]
        which are equal to [0.33, 0.66, 1.0] respectively.
        """
        speed = self.wink.current_fan_speed()
        if speed <= 0.33:
            return FAN_LOW
        if speed <= 0.66:
            return FAN_MEDIUM
        return FAN_HIGH

    @property
    def fan_modes(self):
        """Return a list of available fan modes."""
        return SUPPORT_FAN_AC

    def set_fan_mode(self, fan_mode):
        """
        Set fan speed.

        The official Wink app only supports 3 modes [low, medium, high]
        which are equal to [0.33, 0.66, 1.0] respectively.
        """
        if fan_mode == FAN_LOW:
            speed = 0.33
        elif fan_mode == FAN_MEDIUM:
            speed = 0.66
        elif fan_mode == FAN_HIGH:
            speed = 1.0
        self.wink.set_ac_fan_speed(speed)
