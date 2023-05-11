"""Number entity containing a PID regulator."""
from __future__ import annotations

import logging
import math
from typing import Any

from dvg_pid_controller import Constants as PID_CONST
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
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import PLATFORMS, PidBaseClass
from .const import (
    ATTR_INPUT1,
    ATTR_INPUT2,
    ATTR_OUTPUT,
    ATTR_PID_ENABLE,
    CONF_CYCLE_TIME,
    CONF_INPUT1,
    CONF_INPUT2,
    CONF_OUTPUT,
    CONF_PID_DIR,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_STEP,
    DEFAULT_CYCLE_TIME,
    DEFAULT_MODE,
    DEFAULT_PID_DIR,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DOMAIN,
    MODE_AUTO,
    MODE_BOX,
    MODE_SLIDER,
    PID_DIR_DIRECT,
    PID_DIR_REVERSE,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_CYCLE_TIME, default=DEFAULT_CYCLE_TIME): cv.time_period_dict,
        vol.Required(CONF_INPUT1): cv.entity_id,
        vol.Optional(CONF_INPUT2, default=""): cv.string,
        vol.Required(CONF_OUTPUT): cv.entity_id,
        vol.Optional(CONF_PID_KP, default=DEFAULT_PID_KP): vol.Coerce(float),
        vol.Optional(CONF_PID_KI, default=DEFAULT_PID_KI): vol.Coerce(float),
        vol.Optional(CONF_PID_KD, default=DEFAULT_PID_KD): vol.Coerce(float),
        vol.Optional(CONF_PID_DIR, default=DEFAULT_PID_DIR): vol.In(
            [PID_DIR_DIRECT, PID_DIR_REVERSE]
        ),
        vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN_VALUE): vol.Coerce(float),
        vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX_VALUE): vol.Coerce(float),
        vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_float,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(
            [MODE_BOX, MODE_SLIDER, MODE_AUTO]
        ),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)
DEBUG_PID = False


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize PID Controller config entry."""
    async_add_entities([PidEntity(config_entry.options, config_entry.entry_id)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the number platform."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    async_add_entities([PidEntity(config, config.get(CONF_UNIQUE_ID))])


class PidEntity(RestoreNumber, PidBaseClass):
    """Representation of a PID Controller number."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, config, unique_id: str | None) -> None:
        """Initialize the PID Controller number."""
        self._config = config
        self._attr_native_min_value = config.get(CONF_MINIMUM, DEFAULT_MIN_VALUE)
        self._attr_native_max_value = config.get(CONF_MAXIMUM, DEFAULT_MAX_VALUE)
        self._attr_native_step = config.get(CONF_STEP, DEFAULT_STEP)
        self._attr_mode = config.get(CONF_MODE, DEFAULT_MODE)
        self._attr_last_cycle_start = str(dt_util.utcnow().replace(microsecond=0))
        self._attr_timed_output = ("", 0.0)
        self._output = config[CONF_OUTPUT]
        self._input_1 = config[CONF_INPUT1]
        self._input_2 = config.get(CONF_INPUT2, "")
        self._attr_unique_id = unique_id
        self._output_step = 0.01
        # Use super to create _pid
        super().__init__(
            config.get(CONF_PID_KP, DEFAULT_PID_KP),
            config.get(CONF_PID_KI, DEFAULT_PID_KI),
            config.get(CONF_PID_KD, DEFAULT_PID_KD),
            PID_CONST.DIRECT
            if config.get(CONF_PID_DIR, DEFAULT_PID_DIR) == PID_DIR_DIRECT
            else PID_CONST.REVERSE,
            config.get(CONF_CYCLE_TIME, DEFAULT_CYCLE_TIME),
        )
        # setpoint initial to minimum value
        self._pid.setpoint = self._attr_native_min_value
        self._attr_native_value = self._pid.setpoint

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        start_pid_controller = False
        # Restore state and cycle timer info
        if last_state := await self.async_get_last_state():
            try:
                # restore the enabled state
                start_pid_controller = last_state.attributes.get(ATTR_PID_ENABLE, False)
                await self.async_set_native_value(float(last_state.state))
            except (ValueError, TypeError) as ex:
                _LOGGER.warning(
                    "Failed to restore last state for %s: %s!", self.name, ex
                )

        # After full startup, set outputs and timers & communicate
        # states to the physical outputs
        @callback
        async def _async_startup(*_):
            # Request min- and max values from HA, and clip the output
            # of the PID regulator to that
            entity = self.hass.states.get(self._output)
            if entity:
                attr_min = entity.attributes.get("min", 0.0)
                attr_max = entity.attributes.get("max", 100.0)
                self._output_step = entity.attributes.get("step", 0.01)
                # Set min/max for output
                self._pid.set_output_limits(attr_min, attr_max)
            # Start PID controller cycles
            await self._async_start_pid_cycle()
            if start_pid_controller:
                await self.async_enable(True)

        if self.hass.state == CoreState.running:
            await _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._config[CONF_NAME]

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if math.isnan(value):
            _LOGGER.warning(
                "PID controller %s received invalid value: %s!", self.name, value
            )
        else:
            self._pid.setpoint = value
            self._attr_native_value = self._pid.setpoint
            self.schedule_update_ha_state()

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        attr = super().capability_attributes
        attr.update(super().pid_capability_attributes)
        attr[ATTR_INPUT1] = self.input_1
        attr[ATTR_INPUT2] = self.input_2
        attr[ATTR_OUTPUT] = self.output
        return attr

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        attr_id = self._attr_unique_id or ""
        return DeviceInfo(
            identifiers={(DOMAIN, attr_id)},
            name=self.name,
        )

    async def async_enable(self, value: bool):
        """Enable or disable PID regulator."""
        mode = PID_CONST.MANUAL
        if value:
            mode = PID_CONST.AUTOMATIC
        input_2 = math.nan
        if self._input_2:
            state_i2 = self.hass.states.get(self._input_2)
            if state_i2:
                input_2 = float(state_i2.state)
        state_i1 = self.hass.states.get(self._input_1)
        state_o = self.hass.states.get(self._output)
        if state_i1 and state_o:
            self._pid.set_mode(
                mode,
                float(state_i1.state),
                float(state_o.state),
                input_2,
            )

    @property
    def input_1(self) -> str:
        """Return input 1 entity name."""
        return self._input_1

    @property
    def input_2(self) -> str:
        """Return input 2 entity name."""
        return self._input_2

    @property
    def output(self) -> str:
        """Return output entity name."""
        return self._output

    @callback
    async def _async_pid_cycle(self, args=None):
        """Cycle for PWM timed output."""
        input_1_state = self.hass.states.get(self._input_1)
        if input_1_state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            _LOGGER.warning(
                "Cannot fetch state of input %s for %s", self._input_1, self.name
            )
        else:
            input_1 = float(input_1_state.state)

            input_2 = math.nan
            if self._input_2:
                input_2_state = self.hass.states.get(self._input_2)
                if input_2_state in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
                    _LOGGER.warning(
                        "Cannot fetch state of input %s for %s",
                        self._input_2,
                        self.name,
                    )
                else:
                    input_2 = float(input_2_state.state)
            if not self._pid.compute(input_1, input_2):
                if self._pid.in_auto:
                    _LOGGER.warning(
                        "Something wrong with PID regulator"
                        "%s when calculating from inputs %s and %s!",
                        self.name,
                        input_1,
                        input_2,
                    )
            else:
                pid_val = (
                    round(self._pid.output / self._output_step) * self._output_step
                )  # Round off to step
                state = self.hass.states.get(
                    self._output
                )  # Copy attributes when writing new state (required for UI)
                attr = {}
                if state:
                    attr = state.attributes.copy()
                self.hass.states.async_set(
                    self._output, pid_val, attr
                )  # Use set-state to be as much type-independent as possible

        self._attr_last_cycle_start = dt_util.utcnow().replace(microsecond=0)
        self.async_write_ha_state()
