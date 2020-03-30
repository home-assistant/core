"""Slow-pwm analog output platform."""
import logging

import voluptuous as vol

# from homeassistant.helpers.entity import ToggleEntity
# from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components.analog_output import PLATFORM_SCHEMA, AnalogOutputDevice
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE,
    CONF_MAXIMUM,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_interval,
)
import homeassistant.util.dt as dt_util

CONF_CYCLETIME = "cycletime"
CONF_UP_THRES = "upper_threshold"
CONF_LOW_THRES = "lower_threshold"

EVENT_PWM_SWITCH_ON = "pwm.switch_on"
EVENT_PWM_SWITCH_OFF = "pwm.startcycle"

SERVICE_CYCLE = "cycle"

_LOGGER = logging.getLogger(__name__)
DOMAIN = "slow_pwm"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_CYCLETIME, default="00:30:00"): cv.time_period,
        vol.Optional(CONF_MAXIMUM, default=100): vol.Coerce(float),
        vol.Optional(CONF_UP_THRES, default=100): cv.positive_int,
        vol.Optional(CONF_LOW_THRES, default=0): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    add_entities([SlowPWM(hass, config)])


class SlowPWM(AnalogOutputDevice):
    """Slow-PWM analog output class."""

    def __init__(self, hass, config):
        """Initialize slow-pwm analog output class."""
        super().__init__(config)
        self._hass = hass
        self._listener_on = None
        self._listener_off = None
        self._switch_on_time = None
        self._switch_off_time = None

    async def async_added_to_hass(self):
        """Call when entity is about to be added to Home Assistant."""
        # If not None, we got an initial value.
        async def ha_started(event):
            if self.is_on:
                await self.turn_on()

        # Listen for Homeassistant is started (and we can expect that it is safe to switch
        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, ha_started)

    async def turn_on(self, **kwargs):
        """Turn the switch on."""
        # Set value in parent instance
        await super().turn_on(**kwargs)
        # If still a cycle is running, switch it off
        await self._stop_pwm_cycle()
        # Start up the PWM cycle, but only if above lower threshold, and below upper threshold
        if (self._value >= self._config[CONF_LOW_THRES]) and (
            self._value <= self._config[CONF_UP_THRES]
        ):
            self._listener_on = async_track_time_interval(
                self.hass, self.async_cycle_on, self._config[CONF_CYCLETIME]
            )
            # Run first cycle manual
            await self.async_cycle_on()
        # If we are above the upper threshold, switch continuous on.
        if self._value > self._config[CONF_UP_THRES]:
            await self._switch_on()

    async def turn_off(self, **kwargs):
        """Turn the switch off."""
        await super().turn_off(**kwargs)
        await self._stop_pwm_cycle()

    async def async_set_value(self, value):
        """Set new value."""
        cycle_loop_was_running = (
            self.is_on
            and (self._value >= self._config[CONF_LOW_THRES])
            and (self._value <= self._config[CONF_UP_THRES])
            and self._switch_on_time is not None
        )
        await super().async_set_value(value)
        # Only do something if state is switched-on after
        if self.is_on:
            if not cycle_loop_was_running:
                await self.turn_on()
            elif self._value < self._config[CONF_LOW_THRES]:
                await self._stop_pwm_cycle()
            elif self._value > self._config[CONF_UP_THRES]:
                await self._stop_pwm_cycle()  # Stop cycle
                await self._switch_on()  # Turn continuous on
            else:
                new_off_time = self._switch_on_time + (
                    self._config[CONF_CYCLETIME] * self._value
                ) / (self.maximum - self.minimum)
                if new_off_time > self._switch_off_time:
                    # Delay switch off function
                    await self.async_cycle_on(False)
                else:
                    # Switch off, switching on will be automatically done in cycle loop
                    if self._listener_off is not None:
                        self._listener_off()
                        self._listener_off = None
                    await self._switch_off()
        else:
            if cycle_loop_was_running:
                await self._stop_pwm_cycle()
        self.async_write_ha_state()

    @callback
    async def async_cycle_on(self, new_start=True):
        """Do a pwm cycle."""
        # If running before off-switch: cancel off-switch
        if self._listener_off:
            self._listener_off()
            self._listener_off = None
        # Register switch-off event
        if new_start or (self._switch_on_time is None):
            self._switch_on_time = dt_util.utcnow().replace(microsecond=0)
        self._switch_off_time = self._switch_on_time + (
            self._config[CONF_CYCLETIME] * self._value
        ) / (self.maximum - self.minimum)
        self._listener_off = async_track_point_in_utc_time(
            self.hass, self.async_cycle_off, self._switch_off_time
        )
        await self._switch_on()
        self.async_write_ha_state()

    @callback
    async def async_cycle_off(self, args=None):
        """Switch output off."""
        await self._switch_off()
        self._listener_off = None
        self.async_write_ha_state()

    async def _switch_off(self):
        # Notify that we switch off
        self.hass.bus.async_fire(EVENT_PWM_SWITCH_OFF, {"entity_id": self.entity_id})
        # Turn off the required switch
        service_data = {ATTR_ENTITY_ID: self._config[CONF_DEVICE]}
        await self._hass.services.async_call(
            "switch", SERVICE_TURN_OFF, service_data, False
        )

    async def _switch_on(self):
        # Notify that we switch on
        self.hass.bus.async_fire(EVENT_PWM_SWITCH_ON, {"entity_id": self.entity_id})
        # Turn on the required switch
        service_data = {ATTR_ENTITY_ID: self._config[CONF_DEVICE]}
        await self._hass.services.async_call(
            "switch", SERVICE_TURN_ON, service_data, False
        )

    async def _stop_pwm_cycle(self):
        # Stop the pwm cycle
        if self._listener_on is not None:
            self._listener_on()
            self._listener_on = None
        # Stop the off-switching timer
        if self._listener_off is not None:
            self._listener_off()
            self._listener_off = None

        # Switch off the IO
        await self._switch_off()
