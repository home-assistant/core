"""Number entity containing a slow_pwm number."""
from __future__ import annotations

import logging
from math import floor
from typing import Any

import voluptuous as vol

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    PLATFORM_SCHEMA,
    NumberEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_CYCLE_TIME,
    ATTR_LAST_CYCLE_START,
    ATTR_MIN_SWITCH_TIME,
    ATTR_OUTPUT_STATES,
    ATTR_TIMED_OUTPUT,
    CONF_CYCLE_TIME,
    CONF_MIN_SWITCH_TIME,
    CONF_NUMBERS,
    CONF_OUTPUTS,
    CONF_STEP,
    MODE_AUTO,
    MODE_BOX,
    MODE_SLIDER,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NUMBERS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_OUTPUTS): vol.All(
                        cv.ensure_list,
                        [{vol.Required(CONF_ENTITY_ID): cv.string}],
                    ),
                    vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN_VALUE): vol.Coerce(
                        float
                    ),
                    vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX_VALUE): vol.Coerce(
                        float
                    ),
                    vol.Optional(CONF_CYCLE_TIME, default="00:30:00"): cv.time_period,
                    vol.Optional(
                        CONF_MIN_SWITCH_TIME, default="00:05:00"
                    ): cv.time_period,
                    vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_float,
                    vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In(
                        [MODE_BOX, MODE_SLIDER, MODE_AUTO]
                    ),
                }
            ],
        )
    }
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    numbers = []
    for number_conf in config[CONF_NUMBERS]:
        numbers.append(SlowPWMEntity(hass, number_conf))
    add_entities(numbers)


class SlowPWMEntity(NumberEntity, RestoreEntity):
    """Representation of a Slow PWM number."""

    def __init__(self, hass, config):
        """Initialize the Slow PWM number."""
        self._config = config
        self._hass = hass
        self._attr_min_value = config[CONF_MINIMUM]
        self._attr_max_value = config[CONF_MAXIMUM]
        self._attr_step = config[CONF_STEP]
        self._attr_mode = config[CONF_MODE]
        self._attr_cycle_time = config[CONF_CYCLE_TIME]
        self._attr_min_switch_time = config[CONF_MIN_SWITCH_TIME]
        self._attr_value = config[CONF_MINIMUM]  # initial to minimum value
        self._attr_last_cycle_start = dt_util.utcnow().replace(microsecond=0)
        self._attr_timed_output = ("", 0.0)
        self._outputs = {}
        for output in config[CONF_OUTPUTS]:
            self._outputs[output[CONF_ENTITY_ID]] = False
        super().__init__()
        # Set listeners to None on init
        self._listener_cycle = None
        self._listener_off = None
        self._listener_trigger = None
        self._new_pwm_start = True

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        # Restore state and cycle timer info
        if last_state := await self.async_get_last_state():
            self._attr_value = float(last_state.state)
            self._attr_last_cycle_start = dt_util.parse_datetime(
                last_state.attributes.get(
                    ATTR_LAST_CYCLE_START, str(dt_util.utcnow().replace(microsecond=0))
                )
            )

        # After full startup, set outputs and timers & communicate states to the physical outputs
        async def ha_started(event):
            await self.async_set_value(self._attr_value)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, ha_started)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._config[CONF_NAME]

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        if value <= self._attr_min_value:
            self._attr_value = self._attr_min_value
            await self._async_set_all(False)  # Smallest possible value: set all off
            self.async_write_ha_state()
            return
        if value >= self._attr_max_value:
            self._attr_value = self._attr_max_value
            await self._async_set_all(
                True
            )  # Largest possible value: set all continuously on
            self.async_write_ha_state()
            return
        val_range = self._attr_max_value - self._attr_min_value
        outputs = len(self._outputs)
        range_per_output = val_range / outputs
        output_thres = self._attr_min_value
        last = ""
        for output in self._outputs:
            self._outputs[output] = (
                value > output_thres
            )  # Decide if this output will be on
            output_thres += range_per_output
            if self._outputs[output]:
                last = output  # Remember the output we have set last
        # From now calculate the amount of time the timed-output should be on
        on_normalized = value / val_range
        output_normalized = 1.0 / outputs
        remaining = (
            on_normalized
            - (floor(on_normalized / output_normalized) * output_normalized)
        ) * outputs
        if round(remaining, 2) > 0:
            minimal = self._attr_min_switch_time / self._attr_cycle_time
            remaining = max(remaining, minimal)  # Increase to minimal time on
            if (1.0 - remaining) < minimal:
                self._attr_timed_output = ("", 0.0)  # Just leave it continuously on
            else:
                self._attr_timed_output = (
                    last,
                    remaining,
                )  # It fits in boundaries; notify what output should be on for what (normalized) time
        else:
            self._attr_timed_output = ("", 0.0)
        await self._async_apply()  # Set outputs
        # If a timer loop is required; start PWM loop. If not (e.g. 0%, 100% or a multiple of the groups) stop it.
        if self._attr_timed_output[0]:
            await self._async_pwm_start()
        else:
            await self._async_pwm_stop()
        self._attr_value = value
        self.async_write_ha_state()

    async def _async_set_all(self, value: bool):
        """Set all outputs."""
        for output in self._outputs:
            self._outputs[output] = value
        self._attr_timed_output = ("", 0.0)  # all are on or or off; no timed output
        await self._async_apply()

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
        return self._outputs  # Use copy to force refresh by HA

    @property
    def timed_output(self) -> tuple[str, float]:
        """Return the name of the output entity that will be time-pulsed, and its normalized high-period."""
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

    async def _async_apply(self):
        """Set outputs accordingly to output states by service calls to hass."""
        # Check where in the cycle we are: before or after the high time?
        for output, switch_on in self._outputs.items():
            action = SERVICE_TURN_ON if switch_on else SERVICE_TURN_OFF
            service_data = {ATTR_ENTITY_ID: output}
            await self._hass.services.async_call(
                "homeassistant", action, service_data, False
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
                self.hass, self._async_pwm_off, next_off
            )
            # Set timed output high till that moment
            self._outputs[self._attr_timed_output[0]] = True
            await self._hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self._attr_timed_output[0]},
                False,
            )
        elif self._attr_timed_output[0]:
            # Make sure output is switched off as the off-moment was already passed
            self._outputs[self._attr_timed_output[0]] = False
            await self._hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._attr_timed_output[0]},
                False,
            )
        self.async_write_ha_state()

    @callback
    async def _async_pwm_off(self, args=None):
        """Switch off PWM timed output."""
        if self._attr_timed_output[0]:
            self._outputs[
                self._attr_timed_output[0]
            ] = False  # HA won't update for some reason... why???
            await self._hass.services.async_call(
                "homeassistant",
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._attr_timed_output[0]},
                False,
            )
        self._listener_off = None
        self.async_write_ha_state()
