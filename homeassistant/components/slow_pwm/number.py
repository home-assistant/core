"""Number entity containing a slow_pwm number."""
from __future__ import annotations

from datetime import timedelta
import logging
from math import isnan
from typing import Any

import voluptuous as vol

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    PLATFORM_SCHEMA,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import CoreState, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_interval,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import PLATFORMS
from .const import (
    ATTR_CYCLE_TIME,
    ATTR_LAST_CYCLE_START,
    ATTR_MIN_SWITCH_TIME,
    ATTR_OUTPUT_STATES,
    ATTR_TIMED_OUTPUT,
    CONF_CYCLE_TIME,
    CONF_MIN_SWITCH_TIME,
    CONF_OUTPUTS,
    CONF_STEP,
    DEFAULT_CYCLE_TIME,
    DEFAULT_MODE,
    DEFAULT_SWITCH_TIME,
    DOMAIN,
    MODE_AUTO,
    MODE_BOX,
    MODE_SLIDER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_OUTPUTS): cv.entity_ids,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN_VALUE): vol.Coerce(float),
        vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX_VALUE): vol.Coerce(float),
        vol.Optional(CONF_CYCLE_TIME, default=DEFAULT_CYCLE_TIME): cv.time_period_dict,
        vol.Optional(
            CONF_MIN_SWITCH_TIME, default=DEFAULT_SWITCH_TIME
        ): cv.time_period_dict,
        vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_float,
        vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In(
            [MODE_BOX, MODE_SLIDER, MODE_AUTO]
        ),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize SlowPWM config entry."""
    async_add_entities(
        [SlowPWMEntity(hass, config_entry.options, config_entry.entry_id)]
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    async_add_entities([SlowPWMEntity(hass, config, config.get(CONF_UNIQUE_ID))])


class SlowPWMEntity(RestoreNumber):
    """Representation of a Slow PWM number."""

    def __init__(self, hass: HomeAssistant, config, unique_id: str | None) -> None:
        """Initialize the Slow PWM number."""
        self._config = config
        self._hass = hass
        self._attr_name = config.get(CONF_NAME, "SLOW_PWM_NUMBER")
        self._attr_unique_id = unique_id
        self._attr_native_min_value = config.get(CONF_MINIMUM, DEFAULT_MIN_VALUE)
        self._attr_native_max_value = config.get(CONF_MAXIMUM, DEFAULT_MAX_VALUE)
        self._attr_native_step = config.get(CONF_STEP, DEFAULT_STEP)
        self._attr_mode = config.get(CONF_MODE, DEFAULT_MODE)
        # Issue: config_flow generates dict, cv.time_period generates timestring
        # during pytests. How to handle this?
        cycle_time = config.get(CONF_CYCLE_TIME, DEFAULT_CYCLE_TIME)
        if isinstance(cycle_time, timedelta):
            self._attr_cycle_time = cycle_time
        else:
            self._attr_cycle_time = timedelta(**cycle_time)
        min_switch_time = config.get(CONF_MIN_SWITCH_TIME, DEFAULT_SWITCH_TIME)
        if isinstance(min_switch_time, timedelta):
            self._attr_min_switch_time = min_switch_time
        else:
            self._attr_min_switch_time = timedelta(**min_switch_time)
        self._attr_native_value = config.get(
            CONF_MINIMUM, DEFAULT_MIN_VALUE
        )  # initial to minimum value
        self._attr_last_cycle_start = dt_util.utcnow().replace(microsecond=0)
        self._attr_timed_output = ("", 0.0)
        self._outputs = {}
        for output in config[CONF_OUTPUTS]:
            self._outputs[output] = False
        super().__init__()
        # Set listeners to None on init
        self._listener_cycle = None
        self._listener_off = None
        self._listener_trigger = None
        self._new_pwm_start = True
        # Set some pre-calculculated values.
        # As min- and max value, cycle- and switch time do not change during lifecycle,
        # calculate only once.
        self._range = self._attr_native_max_value - self._attr_native_min_value
        self._range_per_output = self._range / len(self._outputs)
        self._minimal_switch_value = (
            self._attr_min_switch_time / self._attr_cycle_time
        ) * self._range
        self._minimal_on_value = (
            self._attr_native_min_value + self._minimal_switch_value
        )
        self._maximal_on_value = (
            self._attr_native_max_value - self._minimal_switch_value
        )

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        # Restore state and cycle timer info
        if last_data := await self.async_get_last_number_data():
            self._attr_native_value = float(last_data.native_value)

        if last_state := await self.async_get_last_state():
            self._attr_last_cycle_start = dt_util.parse_datetime(
                last_state.attributes.get(
                    ATTR_LAST_CYCLE_START, str(dt_util.utcnow().replace(microsecond=0))
                )
            )

        # After full startup, set outputs and timers & communicate states to the physical outputs
        async def _async_startup(_event=None):
            await self.async_set_native_value(self._attr_native_value)

        if self.hass.state == CoreState.running:
            await _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    async def async_will_remove_from_hass(self):
        """Handle entity about to be removed from hass."""
        await super().async_will_remove_from_hass()
        # Stop timers
        await self._async_pwm_stop()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if isnan(value):
            _LOGGER.warning("Invalid value for SlowPWM: %s", value)
            return
        if value <= self._minimal_on_value:  # Disable PWM cycles, all outputs low
            self._attr_native_value = value
            await self._async_pwm_stop()
            self._attr_timed_output = ("", 0.0)  # Just leave it continuously off
            await self._async_set_all(False)  # Smallest possible value: set all off
            self.async_write_ha_state()
            return
        if value >= self._maximal_on_value:  # Disable PWM cycles, all outputs high
            self._attr_native_value = value
            await self._async_pwm_stop()
            self._attr_timed_output = ("", 0.0)  # Just leave it continuously off
            await self._async_set_all(
                True
            )  # Largest possible value: set all continuously on
            self.async_write_ha_state()
            return

        # Calculate what outputs should be continuously on,
        # what outputs should be off, and what should be timed
        threshold = (
            self._attr_native_min_value - self._minimal_switch_value
        )  # clip on minimal switch time; in this case output will be on.
        timed_output = ""
        for output in self._outputs:
            self._outputs[output] = (
                value >= threshold
            )  # Decide if this output will be on
            if self._outputs[output]:
                threshold += self._range_per_output
                timed_output = output

        # From now calculate the normalized amount the timed-output should be on
        threshold = threshold + self._minimal_switch_value
        normalized_on = round(
            ((value % self._range_per_output) / self._range_per_output), 2
        )

        # Clip in case out of boundaries
        if (normalized_on * self._range_per_output) > self._minimal_switch_value:
            self._attr_timed_output = (timed_output, normalized_on)
        else:
            self._outputs[
                timed_output
            ] = False  # b) clip also on minimal switch time. In this case output off.
            self._attr_timed_output = ("", 0.0)

        # If a timer loop is required; start PWM loop.
        # If not (e.g. 0%, 100% or a multiple of the groups) stop it.
        if self._attr_timed_output[0]:
            await self._async_pwm_start()
        else:
            await self._async_pwm_stop()

        await self._async_apply_outputs()  # Set outputs accordingly
        self._attr_native_value = value
        self.async_write_ha_state()

    async def _async_set_all(self, value: bool):
        """Set all outputs."""
        for output in self._outputs:
            self._outputs[output] = value
        self._attr_timed_output = ("", 0.0)  # all are on or or off; no timed output
        await self._async_apply_outputs()

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        attr = super().capability_attributes
        attr[ATTR_CYCLE_TIME] = self.cycle_time
        attr[ATTR_MIN_SWITCH_TIME] = self.min_switch_time
        return attr

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        # Super does not have state attributes, so create new
        return {
            ATTR_OUTPUT_STATES: self.output_states,
            ATTR_TIMED_OUTPUT: self.timed_output,
            ATTR_LAST_CYCLE_START: self.last_cycle_start,
        }

    @property
    def output_states(self) -> dict[str, Any]:
        """Return output names and their states."""
        return self._outputs

    @property
    def timed_output(self) -> tuple[str, float]:
        """Return the name and normalized high period of the time-pulsed output."""
        return self._attr_timed_output

    @property
    def cycle_time(self) -> str:
        """Return cycle time for PWM generator."""
        return str(self._attr_cycle_time)

    @property
    def last_cycle_start(self) -> str:
        """Return last cycle start time."""
        return str(self._attr_last_cycle_start)

    @property
    def min_switch_time(self) -> str:
        """Return minimal time required for switching on- or off."""
        return str(self._attr_min_switch_time)

    async def _async_apply_outputs(self):
        """Set outputs accordingly to output states by service calls to hass."""
        for output, switch_on in self._outputs.items():
            action = SERVICE_TURN_ON if switch_on else SERVICE_TURN_OFF
            service_data = {ATTR_ENTITY_ID: output}
            await self._hass.services.async_call(
                "homeassistant", action, service_data, True
            )

    async def _async_pwm_start(self):
        """Start PWM cycles."""
        # Check if we are starting halfway a cylce
        prev_cycle = self._attr_last_cycle_start
        now = dt_util.utcnow().replace(microsecond=0)
        next_cycle = prev_cycle + self._attr_cycle_time
        # Check if new cycle is in the past, if so start from now
        if now > next_cycle:
            self._attr_last_cycle_start = now
            next_cycle = now + self._attr_cycle_time
        # Start PWM at calculated moment
        # Launch via single time trigger, on trigger the cycling will start.
        # This enables a start at a time different from cycling rithm.
        if self._listener_trigger:
            self._listener_trigger()
        self._listener_trigger = async_track_point_in_utc_time(
            self.hass, self._async_pwm_trigger, next_cycle
        )
        # Run a manual pwm_on_cycle to make sure off-trigger will be set if required
        self._new_pwm_start = True
        await self._async_pwm_cycle()

    @callback
    async def _async_pwm_trigger(self, args=None):
        """Launch PWM start to enable launch at pre-defined time."""
        if self._listener_cycle:
            self._listener_cycle()
        self._listener_cycle = async_track_time_interval(
            self.hass, self._async_pwm_cycle, self._attr_cycle_time
        )
        self._listener_trigger = None
        await self._async_pwm_cycle()

    async def _async_pwm_stop(self):
        """Stop PWM cycles."""
        if self._listener_trigger:
            self._listener_trigger()
            self._listener_trigger = None
        if self._listener_cycle:
            self._listener_cycle()
            self._listener_cycle = None
        if self._listener_off:
            self._listener_off()
            self._listener_off = None

    @callback
    async def _async_pwm_cycle(self, args=None):
        """Cycle for PWM timed output."""
        # Calculate switch off time, and if in the future, add a lister to hass
        now = dt_util.utcnow().replace(microsecond=0)
        if self._new_pwm_start:
            self._new_pwm_start = False
        else:
            self._attr_last_cycle_start = now
        next_off = self._attr_last_cycle_start + (
            self._attr_timed_output[1] * self._attr_cycle_time
        )
        if next_off > now:
            # Check if a switch-off listener still exists
            if self._listener_off:
                self._listener_off()
            self._listener_off = async_track_point_in_utc_time(
                self.hass, self._async_pwm_switch_off, next_off
            )
            # Set timed output high till that moment
            self._outputs[self._attr_timed_output[0]] = True
            await self._hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self._attr_timed_output[0]},
                True,
            )
        elif self._attr_timed_output[0]:
            # Make sure output is switched off as the off-moment was already passed
            self._outputs[self._attr_timed_output[0]] = False
            await self._hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._attr_timed_output[0]},
                True,
            )
        self.async_write_ha_state()

    @callback
    async def _async_pwm_switch_off(self, args=None):
        """Switch off PWM timed output."""
        if self._attr_timed_output[0]:
            self._outputs[
                self._attr_timed_output[0]
            ] = False  # HA won't update for some reason... why???
            await self._hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._attr_timed_output[0]},
                True,
            )
        self._listener_off = None
        self.async_write_ha_state()
