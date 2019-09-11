"""Virtual thermostats"""
# import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    # ATTR_PRESET_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    PRESET_NONE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback

# from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change,
    #async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = "Virtual Thermostat"

CONF_HEATER = "heater"
CONF_SENSOR = "sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_TARGET_TEMP = "target_temp"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

PRESET_MODE1 = "mode1"
PRESET_MODE2 = "mode2"
PRESET_MODE3 = "mode3"
PRESET_MODE4 = "mode4"
CONF_INITIAL_PRESET_MODE = "initial_preset_mode"
CONF_MODE1_SHIFT_HEAT = "mode1_shift_heat"
CONF_MODE1_SHIFT_COOL = "mode1_shift_cool"
CONF_MODE2_SHIFT_HEAT = "mode2_shift_heat"
CONF_MODE2_SHIFT_COOL = "mode2_shift_cool"
CONF_MODE3_SHIFT_HEAT = "mode3_shift_heat"
CONF_MODE3_SHIFT_COOL = "mode3_shift_cool"
CONF_MODE4_SHIFT_HEAT = "mode4_shift_heat"
CONF_MODE4_SHIFT_COOL = "mode4_shift_cool"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HEATER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
        vol.Optional(CONF_INITIAL_HVAC_MODE): vol.In(
            [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF]
        ),
        vol.Optional(CONF_INITIAL_PRESET_MODE): vol.In(
            [PRESET_NONE, PRESET_MODE1, PRESET_MODE2, PRESET_MODE3, PRESET_MODE4]
        ),
        vol.Optional(CONF_MODE1_SHIFT_HEAT, default=-2.0): vol.Coerce(float),
        vol.Optional(CONF_MODE1_SHIFT_COOL, default=5.0): vol.Coerce(float),
        vol.Optional(CONF_MODE2_SHIFT_HEAT, default=-2.0): vol.Coerce(float),
        vol.Optional(CONF_MODE2_SHIFT_COOL, default=5.0): vol.Coerce(float),
        vol.Optional(CONF_MODE3_SHIFT_HEAT, default=-2.0): vol.Coerce(float),
        vol.Optional(CONF_MODE3_SHIFT_COOL, default=5.0): vol.Coerce(float),
        vol.Optional(CONF_MODE4_SHIFT_HEAT, default=-2.0): vol.Coerce(float),
        vol.Optional(CONF_MODE4_SHIFT_COOL, default=5.0): vol.Coerce(float),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the virtual thermostat platform."""
    name = config.get(CONF_NAME)
    heater_entity_id = config.get(CONF_HEATER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_temp = config.get(CONF_MIN_TEMP)
    max_temp = config.get(CONF_MAX_TEMP)
    target_temp = config.get(CONF_TARGET_TEMP)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    unit = hass.config.units.temperature_unit

    initial_preset_mode = config.get(CONF_INITIAL_PRESET_MODE)
    mode1_shift_cool = config.get(CONF_MODE1_SHIFT_COOL)
    mode1_shift_heat = config.get(CONF_MODE1_SHIFT_HEAT)
    mode2_shift_cool = config.get(CONF_MODE2_SHIFT_HEAT)
    mode2_shift_heat = config.get(CONF_MODE2_SHIFT_HEAT)
    mode3_shift_cool = config.get(CONF_MODE3_SHIFT_HEAT)
    mode3_shift_heat = config.get(CONF_MODE3_SHIFT_HEAT)
    mode4_shift_cool = config.get(CONF_MODE4_SHIFT_HEAT)
    mode4_shift_heat = config.get(CONF_MODE4_SHIFT_HEAT)

    async_add_entities(
        [
            VirtualThermostat(
                name,
                unit,
                heater_entity_id,
                sensor_entity_id,
                min_temp,
                max_temp,
                target_temp,
                initial_hvac_mode,
                initial_preset_mode,
                mode1_shift_cool,
                mode1_shift_heat,
                mode2_shift_cool,
                mode2_shift_heat,
                mode3_shift_cool,
                mode3_shift_heat,
                mode4_shift_cool,
                mode4_shift_heat,
            )
        ]
    )


class VirtualThermostat(ClimateDevice, RestoreEntity):
    """Representation of a Virtual Thermostat device."""

    def __init__(
        self,
        name,
        unit,
        heater_entity_id,
        sensor_entity_id,
        min_temp,
        max_temp,
        target_temp,
        initial_hvac_mode,
        initial_preset_mode,
        mode1_shift_cool,
        mode1_shift_heat,
        mode2_shift_heat,
        mode2_shift_cool,
        mode3_shift_heat,
        mode3_shift_cool,
        mode4_shift_heat,
        mode4_shift_cool,
    ):
        """Initialize the thermostat."""
        self._name = name
        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id

        self._hvac_mode = initial_hvac_mode
        self._preset_mode = initial_preset_mode
        self._target_temp = target_temp
        self._min_temp = min_temp
        self._max_temp = max_temp

        self.mode1_shift_cool = mode1_shift_cool
        self.mode1_shift_heat = mode1_shift_heat
        self.mode2_shift_heat = mode2_shift_heat
        self.mode2_shift_cool = mode2_shift_cool
        self.mode3_shift_heat = mode3_shift_heat
        self.mode3_shift_cool = mode3_shift_cool
        self.mode4_shift_heat = mode4_shift_heat
        self.mode4_shift_cool = mode4_shift_cool

        self._current_temperature = None
        self._unit = unit

        # self._active = False
        # self._saved_target_temp = target_temp or away_temp
        # if self.ac_mode:
        #     self._hvac_list = [HVAC_MODE_COOL, HVAC_MODE_OFF]
        # else:
        #     self._hvac_list = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        # self._temp_lock = asyncio.Lock()
        # self._away_temp = away_temp
        # self._is_away = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener to track changes from the sensor and the heater's switch
        async_track_state_change(
            self.hass, self.sensor_entity_id, self._async_sensor_temperature_changed
        )
        async_track_state_change(
            self.hass, self.heater_entity_id, self._async_switch_heater_changed
        )

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if sensor_state and sensor_state.state != STATE_UNKNOWN:
                self._async_update_current_temp(sensor_state)
                self.async_schedule_update_ha_state()
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial temperature, restore
            _LOGGER.warning("OLD STATE OBJECT %s", old_state)

            # if self._target_temp is None:
            #     # If we have a previously saved temperature
            #     if old_state.attributes.get(ATTR_TEMPERATURE) is None:
            #         if self.ac_mode:
            #             self._target_temp = self.max_temp
            #         else:
            #             self._target_temp = self.min_temp
            #         _LOGGER.warning(
            #             "Undefined target temperature," "falling back to %s",
            #             self._target_temp,
            #         )
            #     else:
            #         self._target_temp = float(old_state.attributes[ATTR_TEMPERATURE])
            # if old_state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY:
            #     self._is_away = True
            # if not self._hvac_mode and old_state.state:
            #     self._hvac_mode = old_state.state

        else:
            # No previous state, try and restore defaults
            if self._target_temp is None:
                if self._hvac_mode == HVAC_MODE_COOL:
                    self._target_temp = self.max_temp
                else:
                    self._target_temp = self.min_temp
            _LOGGER.info(
                "No previously saved temperature, setting to %s", self._target_temp
            )

        # Set default state to off
        if not self._hvac_mode:
            self._hvac_mode = HVAC_MODE_OFF

        # Set default preset to NONE
        if not self._hvac_mode:
            self._hvac_mode = PRESET_NONE

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._current_temperature

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF

        if not self._is_device_active:
            return CURRENT_HVAC_IDLE

        if self._hvac_mode == HVAC_MODE_COOL:
            return CURRENT_HVAC_COOL

        return CURRENT_HVAC_HEAT

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return [PRESET_NONE, PRESET_MODE1, PRESET_MODE2, PRESET_MODE3, PRESET_MODE4]

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_COOL:
            self._hvac_mode = HVAC_MODE_COOL
            await self._async_control_heating(force=True)
        elif hvac_mode == HVAC_MODE_OFF:
            self._hvac_mode = HVAC_MODE_OFF
            if self._is_device_active:
                await self._async_heater_turn_off()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = temperature
        await self._async_control_heating(force=True)
        await self.async_update_ha_state()

    async def _async_sensor_temperature_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return

        self._async_update_current_temp(new_state)
        await self._async_control_heating()
        await self.async_update_ha_state()

    @callback
    def _async_switch_heater_changed(self, entity_id, old_state, new_state):
        """Handle heater switch state changes."""
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    @callback
    def _async_update_current_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            self._current_temperature = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    async def _async_control_heating(self, time=None, force=False):
        """Check if we need to turn heating on or off."""

        _LOGGER.warning("%s\n%s", self._current_temperature, self._target_temp)

        # async with self._temp_lock:
        #     if not self._active and None not in (
        #         self._current_temperature,
        #         self._target_temp,
        #     ):
        #         self._active = True
        #         _LOGGER.info(
        #             "Obtained current and target temperature. "
        #             "Generic thermostat active. %s, %s",
        #             self._current_temperature,
        #             self._target_temp,
        #         )

        #     if not self._active or self._hvac_mode == HVAC_MODE_OFF:
        #         return

        #     if not force and time is None:
        #         # If the `force` argument is True, we
        #         # ignore `min_cycle_duration`.
        #         # If the `time` argument is not none, we were invoked for
        #         # keep-alive purposes, and `min_cycle_duration` is irrelevant.
        #         if self.min_cycle_duration:
        #             if self._is_device_active:
        #                 current_state = STATE_ON
        #             else:
        #                 current_state = HVAC_MODE_OFF
        #             long_enough = condition.state(
        #                 self.hass,
        #                 self.heater_entity_id,
        #                 current_state,
        #                 self.min_cycle_duration,
        #             )
        #             if not long_enough:
        #                 return

        #     too_cold = (
        #         self._target_temp - self._current_temperature >= self._cold_tolerance
        #     )
        #     too_hot = (
        #         self._current_temperature - self._target_temp >= self._hot_tolerance
        #     )
        #     if self._is_device_active:
        #         if (self.ac_mode and too_cold) or (not self.ac_mode and too_hot):
        #             _LOGGER.info("Turning off heater %s", self.heater_entity_id)
        #             await self._async_heater_turn_off()
        #         elif time is not None:
        #             # The time argument is passed only in keep-alive case
        #             await self._async_heater_turn_on()
        #     else:
        #         if (self.ac_mode and too_hot) or (not self.ac_mode and too_cold):
        #             _LOGGER.info("Turning on heater %s", self.heater_entity_id)
        #             await self._async_heater_turn_on()
        #         elif time is not None:
        #             # The time argument is passed only in keep-alive case
        #             await self._async_heater_turn_off()

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self.hass.states.is_state(self.heater_entity_id, STATE_ON)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode.

        This method must be run in the event loop and returns a coroutine.
        """
        # if preset_mode == PRESET_AWAY and not self._is_away:
        #     self._is_away = True
        #     self._saved_target_temp = self._target_temp
        #     self._target_temp = self._away_temp
        #     await self._async_control_heating(force=True)
        # elif preset_mode == PRESET_NONE and self._is_away:
        #     self._is_away = False
        #     self._target_temp = self._saved_target_temp
        #     await self._async_control_heating(force=True)
        self._preset_mode = preset_mode
        await self.async_update_ha_state()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp:
            return self._min_temp

        # get default temp from super class
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp:
            return self._max_temp

        # Get default temp from super class
        return super().max_temp