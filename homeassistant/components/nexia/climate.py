"""Support for Nexia / Trane XL thermostats."""
import datetime
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_FAN_LIST,
    ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    ATTR_CURRENT_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_AUX_HEAT,
    SUPPORT_HOLD_MODE,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_HUMIDITY,
    ATTR_HOLD_MODE,
    ATTR_AUX_HEAT,
    STATE_COOL,
    STATE_HEAT,
    STATE_IDLE,
)
from homeassistant.const import (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    ATTR_ATTRIBUTION,
    ATTR_TEMPERATURE,
    STATE_OFF,
    ATTR_ENTITY_ID,
)
from homeassistant.util import Throttle
from . import (
    ATTR_MODEL,
    ATTR_FIRMWARE,
    ATTR_THERMOSTAT_NAME,
    ATTR_SETPOINT_STATUS,
    ATTR_ZONE_STATUS,
    ATTR_AIRCLEANER_MODE,
    DOMAIN,
    ATTR_THERMOSTAT_ID,
    ATTR_ZONE_ID,
    ATTRIBUTION,
    DATA_NEXIA,
    NEXIA_DEVICE,
    NEXIA_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SET_AIRCLEANER_MODE = "set_aircleaner_mode"

SET_FAN_MIN_ON_TIME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_AIRCLEANER_MODE): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up climate zones for a Nexia device."""
    thermostat = hass.data[DATA_NEXIA][NEXIA_DEVICE]
    scan_interval = hass.data[DATA_NEXIA][NEXIA_SCAN_INTERVAL]
    zones = []
    for thermostat_id in thermostat.get_thermostat_ids():
        for zone_id in thermostat.get_zone_ids(thermostat_id):
            zones.append(NexiaZone(thermostat, scan_interval, thermostat_id, zone_id))
    add_entities(zones, True)

    def airclaner_set_service(service):
        entity_id = service.data.get(ATTR_ENTITY_ID)
        aircleaner_mode = service.data.get(ATTR_AIRCLEANER_MODE)

        if entity_id:
            target_zones = [zone for zone in zones if zone.entity_id in entity_id]
        else:
            target_zones = zones

        for zone in target_zones:
            zone.set_aircleaner_mode(aircleaner_mode)

    hass.services.register(
        DOMAIN,
        SERVICE_SET_AIRCLEANER_MODE,
        airclaner_set_service,
        schema=SET_FAN_MIN_ON_TIME_SCHEMA,
    )


class NexiaZone(ClimateDevice):
    """Provides Nexia Climate support."""

    def __init__(self, device, scan_interval, thermostat_id, zone):
        """Initialize the thermostat."""
        self._device = device
        self._thermostat_id = thermostat_id
        self._zone = zone
        self._scan_interval = scan_interval
        self.update = Throttle(scan_interval)(self._update)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supported = (
            SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_AWAY_MODE
            | SUPPORT_OPERATION_MODE
            | SUPPORT_FAN_MODE
            | SUPPORT_HOLD_MODE
        )

        if self._device.has_relative_humidity(self._thermostat_id):
            supported |= SUPPORT_TARGET_HUMIDITY

        if self._device.has_emergency_heat(self._thermostat_id):
            supported |= SUPPORT_AUX_HEAT

        return supported

    @property
    def is_fan_on(self):
        """Return true if fan is on."""
        return self._device.is_blower_active(self._thermostat_id)

    @property
    def name(self):
        """ Returns the zone name. """
        return self._device.get_zone_name(self._thermostat_id, self._zone)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return (
            TEMP_CELSIUS
            if self._device.get_unit(self._thermostat_id) == "C"
            else TEMP_FAHRENHEIT
        )

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_zone_temperature(self._thermostat_id, self._zone)

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._device.get_fan_mode(self._thermostat_id)

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._device.FAN_MODES

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self._device.set_fan_mode(fan_mode, self._thermostat_id)

    def set_hold_mode(self, hold_mode):
        """Set new target hold mode."""
        if hold_mode.lower() == "none":
            self._device.call_return_to_schedule(self._thermostat_id, self._zone)
        else:
            self._device.set_zone_preset(hold_mode, self._thermostat_id, self._zone)

    @property
    def current_hold_mode(self):
        return self._device.get_zone_preset(self._thermostat_id, self._zone)

    def set_humidity(self, humidity):
        self._device.set_dehumidify_setpoint(humidity / 100.0, self._thermostat_id)

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if self._device.has_relative_humidity(self._thermostat_id):
            return round(
                self._device.get_relative_humidity(self._thermostat_id) * 100.0, 1
            )
        return "Not supported"

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if (
            self._device.get_zone_current_mode(self._thermostat_id, self._zone)
            == "COOL"
        ):
            return self._device.get_zone_cooling_setpoint(
                self._thermostat_id, self._zone
            )
        return self._device.get_zone_heating_setpoint(self._thermostat_id, self._zone)

    @property
    def current_operation(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        system_status = self._device.get_system_status(self._thermostat_id)
        zone_called = self._device.is_zone_calling(self._thermostat_id, self._zone)

        if (
            self._device.get_zone_requested_mode(self._thermostat_id, self._zone)
            == self._device.OPERATION_MODE_OFF
        ):
            return STATE_OFF
        if not zone_called:
            return STATE_IDLE
        if system_status == self._device.SYSTEM_STATUS_COOL:
            return STATE_COOL
        if system_status == self._device.SYSTEM_STATUS_HEAT:
            return STATE_HEAT
        if system_status == self._device.SYSTEM_STATUS_IDLE:
            return STATE_IDLE
        return "idle"

    @property
    def operation_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self.mode

    @property
    def mode(self):
        """Return current mode, as the user-visible name."""
        return self._device.get_zone_requested_mode(self._thermostat_id, self._zone)

    def set_temperature(self, **kwargs):
        """Set target temperature."""
        new_heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW, None)
        new_cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH, None)
        set_temp = kwargs.get(ATTR_TEMPERATURE, None)

        deadband = self._device.get_deadband(self._thermostat_id)
        cur_cool_temp = self._device.get_zone_cooling_setpoint(
            self._thermostat_id, self._zone
        )
        cur_heat_temp = self._device.get_zone_heating_setpoint(
            self._thermostat_id, self._zone
        )
        (min_temp, max_temp) = self._device.get_setpoint_limits(self._thermostat_id)

        # Check that we're not going to hit any minimum or maximum values
        if new_heat_temp and new_heat_temp + deadband > max_temp:
            new_heat_temp = max_temp - deadband
        if new_cool_temp and new_cool_temp - deadband < min_temp:
            new_cool_temp = min_temp + deadband

        # Check that we're within the deadband range, fix it if we're not
        if new_heat_temp and new_heat_temp != cur_heat_temp:
            if new_cool_temp - new_heat_temp < deadband:
                new_cool_temp = new_heat_temp + deadband
        if new_cool_temp and new_cool_temp != cur_cool_temp:
            if new_cool_temp - new_heat_temp < deadband:
                new_heat_temp = new_cool_temp - deadband

        self._device.set_zone_heat_cool_temp(
            heat_temperature=new_heat_temp,
            cool_temperature=new_cool_temp,
            set_temperature=set_temp,
            thermostat_id=self._thermostat_id,
            zone_id=self._zone,
        )

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""

        (min_temp, max_temp) = self._device.get_setpoint_limits(self._thermostat_id)
        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_FAN_MODE: self._device.get_fan_mode(self._thermostat_id),
            ATTR_OPERATION_MODE: self.mode,
            ATTR_TARGET_TEMP_HIGH: self._device.get_zone_cooling_setpoint(
                self._thermostat_id, self._zone
            ),
            ATTR_TARGET_TEMP_LOW: self._device.get_zone_heating_setpoint(
                self._thermostat_id, self._zone
            ),
            ATTR_TARGET_TEMP_STEP: 1.0
            if self._device.get_unit(self._thermostat_id)
            == self._device.UNIT_FAHRENHEIT
            else 0.5,
            ATTR_MIN_TEMP: min_temp,
            ATTR_MAX_TEMP: max_temp,
            ATTR_FAN_LIST: self._device.FAN_MODES,
            ATTR_OPERATION_LIST: self._device.OPERATION_MODES,
            ATTR_HOLD_MODE: self._device.get_zone_preset(
                self._thermostat_id, self._zone
            ),
            # TODO - Enable HOLD_MODES once the presets can be parsed reliably
            # ATTR_HOLD_MODES: self._device.get_zone_presets(
            # self._thermostat_id, self._zone),
            ATTR_MODEL: self._device.get_thermostat_model(self._thermostat_id),
            ATTR_FIRMWARE: self._device.get_thermostat_firmware(self._thermostat_id),
            ATTR_THERMOSTAT_NAME: self._device.get_thermostat_name(self._thermostat_id),
            ATTR_SETPOINT_STATUS: self._device.get_zone_setpoint_status(
                self._thermostat_id, self._zone
            ),
            ATTR_ZONE_STATUS: self._device.get_zone_status(
                self._thermostat_id, self._zone
            ),
            ATTR_THERMOSTAT_ID: self._thermostat_id,
            ATTR_ZONE_ID: self._zone,
        }

        if self._device.has_emergency_heat(self._thermostat_id):
            data.update(
                {
                    ATTR_AUX_HEAT: "on"
                    if self._device.is_emergency_heat_active(self._thermostat_id)
                    else "off"
                }
            )

        if self._device.has_relative_humidity(self._thermostat_id):
            data.update(
                {
                    ATTR_HUMIDITY: round(
                        self._device.get_dehumidify_setpoint(self._thermostat_id)
                        * 100.0,
                        1,
                    ),
                    ATTR_CURRENT_HUMIDITY: round(
                        self._device.get_relative_humidity(self._thermostat_id) * 100.0,
                        1,
                    ),
                    ATTR_MIN_HUMIDITY: round(
                        self._device.get_humidity_setpoint_limits(self._thermostat_id)[
                            0
                        ]
                        * 100.0,
                        1,
                    ),
                    ATTR_MAX_HUMIDITY: round(
                        self._device.get_humidity_setpoint_limits(self._thermostat_id)[
                            1
                        ]
                        * 100.0,
                        1,
                    ),
                }
            )
        return data

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return (
            self._device.get_zone_preset(self._thermostat_id, self._zone)
            == self._device.PRESET_MODE_AWAY
        )

    def turn_away_mode_on(self):
        """Turn away on. """
        self._device.set_zone_preset(
            self._device.PRESET_MODE_AWAY, self._thermostat_id, self._zone
        )

    def turn_away_mode_off(self):
        """Turn away off."""
        self._device.call_return_to_schedule(self._thermostat_id, self._zone)

    def turn_aux_heat_off(self):
        self._device.set_emergency_heat(False, self._thermostat_id)

    def turn_aux_heat_on(self):
        self._device.set_emergency_heat(True, self._thermostat_id)

    def turn_off(self):
        self.set_operation_mode(self._device.OPERATION_MODE_OFF)

    def turn_on(self):
        self.set_operation_mode(self._device.OPERATION_MODE_AUTO)

    def set_swing_mode(self, swing_mode):
        raise NotImplementedError("set_swing_mode is not supported by this device")

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set the system mode (Cool, Heat, etc)."""
        operation_mode = operation_mode.upper()

        if operation_mode in self._device.OPERATION_MODES:
            self._device.set_zone_mode(operation_mode, self._thermostat_id, self._zone)
        else:
            raise KeyError(
                f"Operation mode {operation_mode} not in the supported "
                + f"operations list {str(self._device.OPERATION_MODES)}"
            )

    def set_aircleaner_mode(self, aircleaner_mode):
        """ Sets the aircleaner mode """
        self._device.set_air_cleaner(aircleaner_mode, self._thermostat_id)

    def _update(self):
        """Update the state."""
        if (
            self._device.last_update is None
            or datetime.datetime.now() - self._device.last_update > self._scan_interval
        ):
            self._device.update()
