"""Support for Honeywell Round Connected and Honeywell Evohome thermostats."""
import logging

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE, ATTR_FAN_LIST,
    ATTR_OPERATION_MODE, ATTR_OPERATION_LIST, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP, ATTR_CURRENT_HUMIDITY, ATTR_MIN_HUMIDITY, ATTR_MAX_HUMIDITY, ATTR_HUMIDITY,
    ATTR_MIN_TEMP, ATTR_MAX_TEMP, SUPPORT_TARGET_TEMPERATURE, SUPPORT_AWAY_MODE, SUPPORT_OPERATION_MODE,
    SUPPORT_AUX_HEAT, SUPPORT_HOLD_MODE, SUPPORT_FAN_MODE, SUPPORT_TARGET_HUMIDITY, ATTR_HOLD_MODE)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_ATTRIBUTION, ATTR_TEMPERATURE)
from . import (DATA_NEXIA, ATTR_DAMPER_STATUS, ATTR_MODEL, ATTR_FIRMWARE, ATTR_THERMOSTAT_NAME, ATTRIBUTION)

_LOGGER = logging.getLogger(__name__)




def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up climate zones for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA]
    zones = [NexiaZone(thermostat, zone_id) for zone_id in thermostat.get_zone_ids()]
    add_entities(zones, True)


class NexiaZone(ClimateDevice):
    """Representation of Nexia Climate Zone."""

    def __init__(self, device, zone):
        """Initialize the thermostat."""
        self._device = device
        self._zone = zone

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supported = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_AWAY_MODE | SUPPORT_OPERATION_MODE | SUPPORT_FAN_MODE |
                     SUPPORT_HOLD_MODE)

        if self._device.has_relative_humidity():
            supported |= SUPPORT_TARGET_HUMIDITY

        if self._device.has_emergency_heat():
            supported |= SUPPORT_AUX_HEAT

        return supported

    @property
    def is_fan_on(self):
        """Return true if fan is on."""
        return self._device.is_blower_active()

    @property
    def name(self):
        """ Returns the zone name. """
        return self._device.get_zone_name(self._zone)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return (TEMP_CELSIUS if self._device.get_unit() == 'C' else TEMP_FAHRENHEIT)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_zone_temperature(self._zone)

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._device.get_fan_mode()

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._device.FAN_MODES

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self._device.set_fan_mode(fan_mode)

    def set_hold_mode(self, hold_mode):
        """Set new target hold mode."""
        self._device.set_zone_preset(self._zone)

    @property
    def current_hold_mode(self):
        return self._device.get_zone_preset(self._zone)

    def set_humidity(self, humidty):
        self._device.set_target_humidity(humidty / 100.0)

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if self._device.has_relative_humidity():
            return round(self._device.get_relative_humidity() * 100.0, 1)
        else:
            return "Not supported"

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._device.get_zone_current_mode(self._zone) == 'COOL':
            return self._device.get_zone_cooling_setpoint(self._zone)
        return self._device.get_zone_heating_setpoint(self._zone)

    @property
    def current_operation(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        zone_status = self._device.get_zone_current_mode(self._zone)
        damper_status = self._device.get_zone_damper_status(self._zone)

        if self._device.get_zone_requested_mode(self._zone) == self._device.OPERATION_MODE_OFF:
            return "off"

        if damper_status == self._device.DAMPER_MODE_CLOSED:
            return "idle"

        if self.is_fan_on and zone_status != self._device.OPERATION_MODE_OFF:
            if zone_status == self._device.STATUS_COOL:
                return "cool"
            elif zone_status == self._device.STATUS_HEAT:
                return "heat"
            else:
                raise KeyError(f"Unexpected zone status: {zone_status}")
        else:
            return "idle"

    @property
    def operation_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self.mode

    @property
    def mode(self):
        """Return current mode, as the user-visible name."""
        return self._device.get_zone_requested_mode(self._zone)

    def set_temperature(self, **kwargs):
        """Set target temperature."""
        new_heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW, None)
        new_cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH, None)
        set_temp = kwargs.get(ATTR_TEMPERATURE, None)

        deadband = self._device.get_deadband()
        cur_cool_temp = self._device.get_zone_cooling_setpoint(self._zone)
        cur_heat_temp = self._device.get_zone_heating_setpoint(self._zone)
        (min_temp, max_temp) = self._device.get_setpoint_limits()

        # Check that we're not going to hit any minimum or maximum values
        if new_heat_temp + deadband > max_temp:
            new_heat_temp = max_temp - deadband
        if new_cool_temp - deadband < min_temp:
            new_cool_temp = min_temp + deadband

        # Check that we're within the deadband range
        if new_heat_temp and new_heat_temp != cur_heat_temp:
            if new_cool_temp - new_heat_temp < deadband:
                new_cool_temp = new_heat_temp + deadband
        if new_cool_temp and new_cool_temp != cur_cool_temp:
            if new_cool_temp - new_heat_temp < deadband:
                new_heat_temp = new_cool_temp - deadband


        self._device.set_zone_cool_heat_temp(heat_temperature=new_heat_temp,
                                             cool_temperature=new_cool_temp,
                                             set_temperature=set_temp,
                                             zone_id=self._zone)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""

        (min_temp, max_temp) = self._device.get_setpoint_limits()
        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_FAN_MODE: self._device.get_fan_mode(),
            ATTR_DAMPER_STATUS: self._device.get_zone_damper_status(self._zone),
            ATTR_OPERATION_MODE: self.mode,
            ATTR_TARGET_TEMP_HIGH: self._device.get_zone_cooling_setpoint(),
            ATTR_TARGET_TEMP_LOW: self._device.get_zone_heating_setpoint(),
            ATTR_TARGET_TEMP_STEP: 1,
            ATTR_MIN_TEMP: min_temp,
            ATTR_MAX_TEMP: max_temp,
            ATTR_FAN_LIST: self._device.FAN_MODES,
            ATTR_OPERATION_LIST: self._device.OPERATION_MODES,
            ATTR_HOLD_MODE: self._device.get_zone_preset(self._zone),
            ATTR_MODEL: self._device.get_thermostat_model(),
            ATTR_FIRMWARE: self._device.get_thermostat_firmware(),
            ATTR_THERMOSTAT_NAME: self._device.get_thermostat_name()
        }

        if self._device.has_relative_humidity():
            data.update({ATTR_HUMIDITY:         round(self._device.get_target_humidity() * 100.0, 1),
                         ATTR_CURRENT_HUMIDITY: round(self._device.get_relative_humidity() * 100.0, 1),
                         ATTR_MIN_HUMIDITY:     round(self._device.get_humidity_setpoint_limits()[0] * 100.0, 1),
                         ATTR_MAX_HUMIDITY:     round(self._device.get_humidity_setpoint_limits()[1] * 100.0, 1),
                         })


        return data


    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._device.get_zone_preset(self._zone) == self._device.PRESET_MODE_AWAY

    def turn_away_mode_on(self):
        """Turn away on. """
        self._device.set_zone_preset(self._device.PRESET_MODE_AWAY, self._zone)

    def turn_away_mode_off(self):
        """Turn away off."""
        self._device.set_zone_hold_setpoints(zone_id=self._zone)

    def turn_aux_heat_off(self):
        self._device.set_emergency_heat(False)

    def turn_aux_heat_on(self):
        self._device.set_emergency_heat(True)

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set the system mode (Cool, Heat, etc)."""
        operation_mode = operation_mode.upper()

        if operation_mode in self._device.OPERATION_MODES:
            self._device.set_zone_mode(operation_mode, self._zone)
        else:
            raise KeyError(f"Operation mode {operation_mode} not in the supported operations list {str(self._device.OPERATION_MODES)}")

    def update(self):
        """Update the state."""
        self._device.update()


