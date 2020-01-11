"""Generic thermostat."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_ENTITY_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, callback
from homeassistant.helpers import condition
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Generic Thermostat"
DEFAULT_TARGET_TEMP_HEAT = 19.0
DEFAULT_TARGET_TEMP_COOL = 28.0
DEFAULT_SHIFT_HEAT = -4.0
DEFAULT_SHIFT_COOL = 4.0
DEFAULT_MAX_TEMP_HEAT = 24
DEFAULT_MIN_TEMP_HEAT = 17
DEFAULT_MAX_TEMP_COOL = 35
DEFAULT_MIN_TEMP_COOL = 20
DEFAULT_INITIAL_HVAC_MODE = HVAC_MODE_OFF
DEFAULT_INITIAL_PRESET_MODE = PRESET_NONE
DEFAULT_HYSTERESIS_TOLERANCE = 0.5
DEFAULT_OLD_STATE = False

CONF_SENSOR = "sensor"
CONF_INITIAL_HVAC_MODE = "initial_hvac_mode"
CONF_INITIAL_PRESET_MODE = "initial_preset_mode"
CONF_KEEP_ALIVE = "keep_alive"
CONF_HYSTERESIS_TOLERANCE_ON = "hysteresis_tolerance_on"
CONF_HYSTERESIS_TOLERANCE_OFF = "hysteresis_tolerance_off"
CONF_HVAC_MODE_MIN_TEMP = "min_temp"
CONF_HVAC_MODE_MAX_TEMP = "max_temp"
CONF_HVAC_MODE_INIT_TEMP = "initial_target_temp"
CONF_ENABLED_PRESETS = "enabled_presets"
CONF_AWAY_TEMP = "away_temp"
CONF_ECO_SHIFT = "eco_shift"
CONF_COMFORT_SHIFT = "comfort_shift"
CONF_MIN_CYCLE_DURATION = "min_cycle_duration"
CONF_ENABLE_OLD_STATE = "restore_from_old_state"

SUPPORTED_HVAC_MODES = [HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_OFF]
SUPPORTED_PRESET_MODES = [PRESET_NONE, PRESET_AWAY, PRESET_ECO, PRESET_COMFORT]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_INITIAL_HVAC_MODE, default=DEFAULT_INITIAL_HVAC_MODE): vol.In(
            SUPPORTED_HVAC_MODES
        ),
        vol.Optional(
            CONF_INITIAL_PRESET_MODE, default=DEFAULT_INITIAL_PRESET_MODE
        ): vol.In(SUPPORTED_PRESET_MODES),
        vol.Optional(
            CONF_HYSTERESIS_TOLERANCE_ON, default=DEFAULT_HYSTERESIS_TOLERANCE
        ): vol.Coerce(float),
        vol.Optional(
            CONF_HYSTERESIS_TOLERANCE_OFF, default=DEFAULT_HYSTERESIS_TOLERANCE
        ): vol.Coerce(float),
        vol.Optional(CONF_KEEP_ALIVE): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(HVAC_MODE_HEAT): vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): cv.entity_id,
                vol.Required(
                    CONF_HVAC_MODE_MIN_TEMP, default=DEFAULT_MIN_TEMP_HEAT
                ): vol.Coerce(float),
                vol.Required(
                    CONF_HVAC_MODE_MAX_TEMP, default=DEFAULT_MAX_TEMP_HEAT
                ): vol.Coerce(float),
                vol.Required(
                    CONF_HVAC_MODE_INIT_TEMP, default=DEFAULT_TARGET_TEMP_HEAT
                ): vol.Coerce(float),
                vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
                vol.Optional(CONF_ECO_SHIFT): vol.Coerce(float),
                vol.Optional(CONF_COMFORT_SHIFT): vol.Coerce(float),
            }
        ),
        vol.Optional(HVAC_MODE_COOL): vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): cv.entity_id,
                vol.Required(
                    CONF_HVAC_MODE_MIN_TEMP, default=DEFAULT_MIN_TEMP_COOL
                ): vol.Coerce(float),
                vol.Required(
                    CONF_HVAC_MODE_MAX_TEMP, default=DEFAULT_MAX_TEMP_COOL
                ): vol.Coerce(float),
                vol.Required(
                    CONF_HVAC_MODE_INIT_TEMP, default=DEFAULT_TARGET_TEMP_COOL
                ): vol.Coerce(float),
                vol.Optional(CONF_AWAY_TEMP): vol.Coerce(float),
                vol.Optional(CONF_ECO_SHIFT): vol.Coerce(float),
                vol.Optional(CONF_COMFORT_SHIFT): vol.Coerce(float),
            }
        ),
        vol.Optional(CONF_ENABLED_PRESETS, default=[]): vol.All(
            cv.ensure_list, SUPPORTED_PRESET_MODES
        ),
        vol.Optional(CONF_MIN_CYCLE_DURATION): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_ENABLE_OLD_STATE, default=DEFAULT_OLD_STATE): cv.boolean,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the generic thermostat platform."""
    name = config.get(CONF_NAME)
    sensor_entity_id = config.get(CONF_SENSOR)
    initial_hvac_mode = config.get(CONF_INITIAL_HVAC_MODE)
    unit = hass.config.units.temperature_unit
    initial_preset_mode = config.get(CONF_INITIAL_PRESET_MODE)
    tolerance_on = config.get(CONF_HYSTERESIS_TOLERANCE_ON)
    tolerance_off = config.get(CONF_HYSTERESIS_TOLERANCE_OFF)
    keep_alive = config.get(CONF_KEEP_ALIVE)
    enabled_presets = config.get(CONF_ENABLED_PRESETS)
    min_cycle_duration = config.get(CONF_MIN_CYCLE_DURATION)
    enable_old_state = config.get(CONF_ENABLE_OLD_STATE)
    heat_conf = config.get(HVAC_MODE_HEAT)
    cool_conf = config.get(HVAC_MODE_COOL)
    enabled_hvac_modes = []

    # Do all the checks I cannot do with voluptuous
    if initial_preset_mode != "none" and initial_preset_mode not in enabled_presets:
        _LOGGER.error(
            "There is no enabled presets and yet an initial_preset has been set (%s)",
            initial_preset_mode,
        )
        return False

    # Check the enabled modes
    if heat_conf:
        enabled_hvac_modes.append(HVAC_MODE_HEAT)
    if cool_conf:
        enabled_hvac_modes.append(HVAC_MODE_COOL)

    if not enabled_hvac_modes:
        _LOGGER.error("You have to set at least one HVAC mode (heat or cold)")
        return False

    if initial_hvac_mode != HVAC_MODE_OFF:
        if initial_hvac_mode not in enabled_hvac_modes:
            _LOGGER.error(
                "You cannot set an initial HVAC mode if you did not configure this mode (%s)",
                initial_hvac_mode,
            )
            return False

    # Check if all the informations for the presets are set, for each enabled mode
    for mode in enabled_hvac_modes:
        if mode == HVAC_MODE_HEAT:
            conf = heat_conf
        elif mode == HVAC_MODE_COOL:
            conf = cool_conf

        if PRESET_AWAY in enabled_presets and CONF_AWAY_TEMP not in conf:
            _LOGGER.error(
                "For hvac mode %s, preset away is configured but %s is not set",
                mode,
                CONF_AWAY_TEMP,
            )
            return False
        if PRESET_ECO in enabled_presets and CONF_ECO_SHIFT not in conf:
            _LOGGER.error(
                "For hvac mode %s, preset eco is configured but %s is not set",
                mode,
                CONF_ECO_SHIFT,
            )
            return False
        if PRESET_COMFORT in enabled_presets and CONF_COMFORT_SHIFT not in conf:
            _LOGGER.error(
                "For hvac mode %s, preset comfort is configured but %s is not set",
                mode,
                CONF_COMFORT_SHIFT,
            )
            return False

    async_add_entities(
        [
            GenericThermostat(
                name,
                unit,
                sensor_entity_id,
                tolerance_on,
                tolerance_off,
                keep_alive,
                heat_conf,
                cool_conf,
                enabled_presets,
                enabled_hvac_modes,
                initial_hvac_mode,
                initial_preset_mode,
                min_cycle_duration,
                enable_old_state,
            )
        ]
    )


class GenericThermostat(ClimateDevice, RestoreEntity):
    """Representation of a Generic Thermostat device."""

    def __init__(
        self,
        name,
        unit,
        sensor_entity_id,
        tolerance_on,
        tolerance_off,
        keep_alive,
        heat_conf,
        cool_conf,
        enabled_presets,
        enabled_hvac_modes,
        initial_hvac_mode,
        initial_preset_mode,
        min_cycle_duration,
        enable_old_state,
    ):
        """Initialize the thermostat."""
        self._name = name
        self._sensor_entity_id = sensor_entity_id
        self._hvac_mode = initial_hvac_mode
        self._preset_mode = initial_preset_mode
        self._enabled_presets = enabled_presets
        self._enabled_hvac_mode = enabled_hvac_modes
        self._min_cycle_duration = min_cycle_duration
        self._enable_old_state = enable_old_state
        self._tolerance_on = tolerance_on
        self._tolerance_off = tolerance_off
        self._unit = unit
        self._keep_alive = keep_alive

        if self._is_heat_enabled:
            self._heat_conf = heat_conf
            self._target_temp_heat = self._heat_conf[CONF_HVAC_MODE_INIT_TEMP]
            self._heater_entity_id = self._heat_conf[CONF_ENTITY_ID]
            _LOGGER.debug(
                "Heat mode enabled; target_temp_heat: %s, entity_id: %s",
                self._target_temp_heat,
                self._heater_entity_id,
            )
        else:
            self._heat_conf = None
            self._target_temp_heat = None
            self._heater_entity_id = None

        if self._is_cool_enabled:
            self._cool_conf = cool_conf
            self._target_temp_cool = self._cool_conf[CONF_HVAC_MODE_INIT_TEMP]
            self._ac_entity_id = self._cool_conf[CONF_ENTITY_ID]
            _LOGGER.debug(
                "Cool mode enabled; _target_temp_cool: %s, entity_id: %s",
                self._target_temp_cool,
                self._ac_entity_id,
            )
        else:
            self._cool_conf = None
            self._target_temp_cool = None
            self._ac_entity_id = None

        self._current_temperature = None
        self._temp_lock = asyncio.Lock()

    async def async_added_to_hass(self):
        """Run when entity about to be added.

        Attach the listeners.
        """
        await super().async_added_to_hass()

        # Add listeners to track changes from the sensor and the heater's switch
        async_track_state_change(
            self.hass, self._sensor_entity_id, self._async_sensor_temperature_changed
        )
        if self._is_heat_enabled:
            async_track_state_change(
                self.hass, self._heater_entity_id, self._async_switch_device_changed
            )
        if self._is_cool_enabled:
            async_track_state_change(
                self.hass, self._ac_entity_id, self._async_switch_device_changed
            )

        if self._keep_alive:
            async_track_time_interval(self.hass, self._async_operate, self._keep_alive)

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self._sensor_entity_id)
            if sensor_state and sensor_state.state != STATE_UNKNOWN:
                self._async_update_current_temp(sensor_state)
                self.async_schedule_update_ha_state()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        _async_startup(None)  # init the sensor

        # Check if we have an old state, if so, restore it
        old_state = await self.async_get_last_state()

        if self._enable_old_state and old_state is not None:
            _LOGGER.debug("Old state stored : %s", old_state)
            old_preset_mode = old_state.attributes.get(ATTR_PRESET_MODE)
            old_hvac_mode = old_state.state
            old_temperature = old_state.attributes.get(ATTR_TEMPERATURE)
            _LOGGER.debug(
                "Old state preset mode %s, hvac mode %s, temperature %s",
                old_preset_mode,
                old_hvac_mode,
                old_temperature,
            )

            if old_preset_mode is not None and old_preset_mode in self.preset_modes:
                self._preset_mode = old_preset_mode

            if old_hvac_mode is not None and old_hvac_mode in self.hvac_modes:
                self._hvac_mode = old_hvac_mode

                # Restore the target temperature
                if old_hvac_mode == HVAC_MODE_COOL:
                    min_temp = self._cool_conf[CONF_HVAC_MODE_MIN_TEMP]
                    max_temp = self._cool_conf[CONF_HVAC_MODE_MAX_TEMP]
                    if (
                        old_temperature is not None
                        and min_temp <= old_temperature <= max_temp
                    ):
                        self._target_temp_cool = old_temperature
                elif old_hvac_mode == HVAC_MODE_HEAT:
                    min_temp = self._heat_conf[CONF_HVAC_MODE_MIN_TEMP]
                    max_temp = self._heat_conf[CONF_HVAC_MODE_MAX_TEMP]
                    if (
                        old_temperature is not None
                        and min_temp <= old_temperature <= max_temp
                    ):
                        self._target_temp_heat = old_temperature

        await self._async_operate()
        await self.async_update_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        # No changes have been made
        if self._hvac_mode == hvac_mode:
            return
        if hvac_mode not in self.hvac_modes:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return
        _LOGGER.debug("HVAC mode changed to %s", hvac_mode)
        self._hvac_mode = hvac_mode
        await self._async_operate()

        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if hvac_mode is None:
            hvac_mode = self._hvac_mode
        elif hvac_mode not in self.hvac_modes:
            _LOGGER.warning(
                "Try to update temperature to %s for mode %s but this mode is not enabled. Skipping.",
                temperature,
                hvac_mode,
            )
            return

        if hvac_mode is None or hvac_mode == HVAC_MODE_OFF:
            _LOGGER.warning("You cannot update temperature for OFF mode")
            return

        _LOGGER.debug(
            "Temperature updated to %s for mode %s", temperature - self.shift, hvac_mode
        )

        if hvac_mode == HVAC_MODE_COOL:
            self._target_temp_cool = temperature - self.shift
        if hvac_mode == HVAC_MODE_HEAT:
            self._target_temp_heat = temperature - self.shift

        if (
            self.preset_mode == PRESET_AWAY
        ):  # when preset mode is away, change the temperature but do not operate
            _LOGGER.debug(
                "Preset mode away when temperature is updated : skipping operate"
            )
            return

        await self._async_operate()
        await self.async_update_ha_state()

    async def _async_sensor_temperature_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        _LOGGER.debug("Sensor temperature updated to %s", new_state.state)
        if new_state.state is None or new_state.state == "None":
            return

        self._async_update_current_temp(new_state)
        await self._async_operate(sensor_changed=True)
        await self.async_update_ha_state()

    @callback
    def _async_switch_device_changed(self, entity_id, old_state, new_state):
        """Handle device switch state changes."""
        _LOGGER.debug(
            "Switch of %s changed from %s to %s", entity_id, old_state, new_state
        )
        if new_state.state is None or new_state.state == "None":
            return
        self.async_schedule_update_ha_state()

    @callback
    def _async_update_current_temp(self, state):
        """Update thermostat with latest state from sensor."""
        try:
            _LOGGER.debug("Current temperature updated to %s", float(state.state))
            self._current_temperature = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    async def _async_operate(self, time=None, sensor_changed=False):
        """Check if we need to turn heating on or off."""
        async with self._temp_lock:
            # time is passed by to the callback the async_track_time_interval function , and is set to "now"
            keepalive = time is not None

            # If the mode is OFF and the device is ON, turn it OFF and exit, else, just exit
            if self._hvac_mode == HVAC_MODE_OFF:
                _LOGGER.debug("HVAC mode is OFF. Turn the devices OFF and exit")
                if self._is_heat_enabled and self._is_heater_active:
                    await self._async_heater_turn_off()
                if self._is_cool_enabled and self._is_ac_active:
                    await self._async_ac_turn_off()
                return

            if self._current_temperature is None:
                _LOGGER.debug("Current temp is None, cannot compare with target")
                return

            # if the call was made by a sensor change, check the min duration
            # in case of keep-alive (time not none) ignore this test, min duration is irrelevant
            if (
                sensor_changed
                and self._min_cycle_duration is not None
                and not keepalive
            ):
                entity_id = self._heater_entity_id
                current_state = (
                    STATE_ON
                    if self._is_heat_enabled and self._is_heater_active
                    else STATE_OFF
                )
                if self._hvac_mode == HVAC_MODE_COOL:
                    entity_id = self._ac_entity_id
                    current_state = (
                        STATE_ON
                        if self._is_cool_enabled and self._is_ac_active
                        else STATE_OFF
                    )

                long_enough = condition.state(
                    self.hass, entity_id, current_state, self._min_cycle_duration
                )

                if not long_enough:
                    _LOGGER.debug(
                        "Operate - Min duration not expired, exiting (%s, %s, %s)",
                        self._min_cycle_duration,
                        current_state,
                        entity_id,
                    )
                    return

            target_temp_min = self.target_temperature  # lower limit
            target_temp_max = self.target_temperature  # upper limit
            if self._hvac_mode == HVAC_MODE_HEAT:
                target_temp_min = target_temp_min - self._tolerance_on
                target_temp_max = target_temp_max + self._tolerance_off
            else:
                target_temp_min = target_temp_min - self._tolerance_off
                target_temp_max = target_temp_max + self._tolerance_on

            current_temp = self._current_temperature

            _LOGGER.debug(
                "Operate - target_temp_min %s, target_temp_max %s, current_temp %s, target_temp %s, shift %s, keepalive %s",
                target_temp_min,
                target_temp_max,
                current_temp,
                self.target_temperature,
                self.shift,
                keepalive,
            )

            # If keep-alive case, we force the order resend (this is the goal of keep alive)
            force_resend = keepalive

            if self._hvac_mode == HVAC_MODE_HEAT:
                if self._is_cool_enabled:
                    await self._async_ac_turn_off(force=force_resend)
                if current_temp > target_temp_max:
                    await self._async_heater_turn_off(force=force_resend)
                elif current_temp <= target_temp_min:
                    await self._async_heater_turn_on(force=force_resend)
            elif self._hvac_mode == HVAC_MODE_COOL:
                if self._is_heat_enabled:
                    await self._async_heater_turn_off(force=force_resend)
                if current_temp >= target_temp_max:
                    await self._async_ac_turn_on(force=force_resend)
                elif current_temp < target_temp_min:
                    await self._async_ac_turn_off(force=force_resend)

    async def _async_heater_turn_on(self, force=False):
        """Turn heater toggleable device on."""
        _LOGGER.debug("Turn Heater ON")
        if self._is_heater_active and not force:
            _LOGGER.debug("Heater already ON")
            return
        data = {ATTR_ENTITY_ID: self._heater_entity_id}
        _LOGGER.debug("Order ON sent to heater device %s", self._heater_entity_id)
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)

    async def _async_heater_turn_off(self, force=False):
        """Turn heater toggleable device off."""
        _LOGGER.debug("Turn Heater OFF called")
        if not self._is_heater_active and not force:
            _LOGGER.debug("Heater already OFF")
            return
        data = {ATTR_ENTITY_ID: self._heater_entity_id}
        _LOGGER.debug("Order OFF sent")
        _LOGGER.debug("Order OFF sent to heater device %s", self._heater_entity_id)
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)

    async def _async_ac_turn_on(self, force=False):
        """Turn ac toggleable device on."""
        _LOGGER.debug("Turn AC ON")
        if self._is_ac_active and not force:
            _LOGGER.debug("AC already ON")
            return
        data = {ATTR_ENTITY_ID: self._ac_entity_id}
        _LOGGER.debug("Order ON sent to AC device %s", self._ac_entity_id)
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)

    async def _async_ac_turn_off(self, force=False):
        """Turn ac toggleable device off."""
        _LOGGER.debug("Turn AC OFF")
        if not self._is_ac_active and not force:
            _LOGGER.debug("AC already OFF")
            return
        data = {ATTR_ENTITY_ID: self._ac_entity_id}
        _LOGGER.debug("Order OFF sent to AC device %s", self._ac_entity_id)
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode.

        This method must be run in the event loop and returns a coroutine.
        """
        if preset_mode in self.preset_modes or preset_mode == PRESET_NONE:
            self._preset_mode = preset_mode
            _LOGGER.debug("Set preset mode to %s", preset_mode)
            await self._async_operate()
            await self.async_update_ha_state()
        else:
            _LOGGER.error(
                "This preset (%s) is not enabled (see the configuration)", preset_mode
            )
            return

    @property
    def shift(self):
        """Return the calculated temperature shift."""
        if self._preset_mode == PRESET_ECO:
            return (
                self._cool_conf[CONF_ECO_SHIFT]
                if self._hvac_mode == HVAC_MODE_COOL
                else self._heat_conf[CONF_ECO_SHIFT]
            )
        if self._preset_mode == PRESET_COMFORT:
            return (
                self._cool_conf[CONF_COMFORT_SHIFT]
                if self._hvac_mode == HVAC_MODE_COOL
                else self._heat_conf[CONF_COMFORT_SHIFT]
            )
        return 0

    @property
    def _is_heater_active(self):
        """If the toggleable heater device is currently active."""
        return self.hass.states.is_state(self._heater_entity_id, STATE_ON)

    @property
    def _is_ac_active(self):
        """If the toggleable AC device is currently active."""
        return self.hass.states.is_state(self._ac_entity_id, STATE_ON)

    @property
    def _is_cool_enabled(self):
        """Is the cool mode enabled."""
        if HVAC_MODE_COOL in self._enabled_hvac_mode:
            return True
        return False

    @property
    def _is_heat_enabled(self):
        """Is the heat mode enabled."""
        if HVAC_MODE_HEAT in self._enabled_hvac_mode:
            return True
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._enabled_presets:
            return SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._hvac_mode == HVAC_MODE_HEAT:
            if self.preset_mode == PRESET_AWAY:
                return self._heat_conf[CONF_AWAY_TEMP]
            return self._heat_conf[CONF_HVAC_MODE_MIN_TEMP] + self.shift
        if self._hvac_mode == HVAC_MODE_COOL:
            if self.preset_mode == PRESET_AWAY:
                return self._cool_conf[CONF_AWAY_TEMP]
            return self._cool_conf[CONF_HVAC_MODE_MIN_TEMP] + self.shift

        # Get default temp from super class
        return super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._hvac_mode == HVAC_MODE_HEAT:
            if self.preset_mode == PRESET_AWAY:
                return self._heat_conf[CONF_AWAY_TEMP]
            return self._heat_conf[CONF_HVAC_MODE_MAX_TEMP] + self.shift
        if self._hvac_mode == HVAC_MODE_COOL:
            if self.preset_mode == PRESET_AWAY:
                return self._cool_conf[CONF_AWAY_TEMP]
            return self._cool_conf[CONF_HVAC_MODE_MAX_TEMP] + self.shift

        # Get default temp from super class
        return super().max_temp

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
        if (
            self._is_cool_enabled
            and self._hvac_mode == HVAC_MODE_COOL
            and self._is_ac_active
        ):
            return CURRENT_HVAC_COOL
        if (
            self._is_heat_enabled
            and self._hvac_mode == HVAC_MODE_HEAT
            and self._is_heater_active
        ):
            return CURRENT_HVAC_HEAT

        return CURRENT_HVAC_IDLE

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._hvac_mode == HVAC_MODE_OFF:
            return None

        if self._preset_mode == PRESET_AWAY:
            return (
                self._cool_conf[CONF_AWAY_TEMP]
                if self._hvac_mode == HVAC_MODE_COOL
                else self._heat_conf[CONF_AWAY_TEMP]
            )

        return (
            self._target_temp_cool + self.shift
            if self._hvac_mode == HVAC_MODE_COOL
            else self._target_temp_heat + self.shift
        )

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._enabled_hvac_mode + [HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return self._preset_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return self._enabled_presets + [PRESET_NONE]
