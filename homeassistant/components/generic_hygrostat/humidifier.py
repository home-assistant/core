"""Adds support for generic hygrostat units."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.humidifier import PLATFORM_SCHEMA, HumidifierDevice
from homeassistant.components.humidifier.const import (
    ATTR_PRESET_MODE,
    ATTR_HUMIDITY,
    CURRENT_HUMIDIFIER_DRY,
    CURRENT_HUMIDIFIER_HUMIDIFY,
    CURRENT_HUMIDIFIER_IDLE,
    CURRENT_HUMIDIFIER_OFF,
    OPERATION_MODE_DRY,
    OPERATION_MODE_HUMIDIFY,
    OPERATION_MODE_OFF,
    PRESET_AWAY,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
    PRESET_NONE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = "Generic Hygrostat"

CONF_HUMIDIFIER = "humidifier"
CONF_SENSOR = "target_sensor"
CONF_MIN_HUMIDITY = "min_humidity"
CONF_MAX_HUMIDITY = "max_humidity"
CONF_TARGET_HUMIDITY = "target_humidity"
CONF_DRY_MODE = "dry_mode"
CONF_MIN_DUR = "min_cycle_duration"
CONF_DRY_TOLERANCE = "dry_tolerance"
CONF_WET_TOLERANCE = "wet_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_OPERATION_MODE = "initial_operation_mode"
CONF_AWAY_HUMIDITY = "away_humidity"
SUPPORT_FLAGS = SUPPORT_TARGET_HUMIDITY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HUMIDIFIER): cv.entity_id,
        vol.Required(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_DRY_MODE): cv.boolean,
        vol.Optional(CONF_MAX_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_MIN_DUR): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_MIN_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DRY_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_WET_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_TARGET_HUMIDITY): vol.Coerce(float),
        vol.Optional(CONF_KEEP_ALIVE): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_INITIAL_OPERATION_MODE): vol.In(
            [OPERATION_MODE_DRY, OPERATION_MODE_HUMIDIFY, OPERATION_MODE_OFF]
        ),
        vol.Optional(CONF_AWAY_HUMIDITY): vol.Coerce(float),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the generic hygrostat platform."""
    name = config.get(CONF_NAME)
    humidifier_entity_id = config.get(CONF_HUMIDIFIER)
    sensor_entity_id = config.get(CONF_SENSOR)
    min_humidity = config.get(CONF_MIN_HUMIDITY)
    max_humidity = config.get(CONF_MAX_HUMIDITY)
    target_humidity = config.get(CONF_TARGET_HUMIDITY)
    dry_mode = config.get(CONF_DRY_MODE)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    dry_tolerance = config.get(CONF_DRY_TOLERANCE)
    wet_tolerance = config.get(CONF_WET_TOLERANCE)
    keep_alive = config.get(CONF_KEEP_ALIVE)
    initial_operation_mode = config.get(CONF_INITIAL_OPERATION_MODE)
    away_humidity = config.get(CONF_AWAY_HUMIDITY)

    async_add_entities(
        [
            GenericHygrostat(
                name,
                humidifier_entity_id,
                sensor_entity_id,
                min_humidity,
                max_humidity,
                target_humidity,
                dry_mode,
                min_cycle_duration,
                dry_tolerance,
                wet_tolerance,
                keep_alive,
                initial_operation_mode,
                away_humidity,
            )
        ]
    )


class GenericHygrostat(HumidifierDevice, RestoreEntity):
    """Representation of a Generic Hygrostat device."""

    def __init__(
        self,
        name,
        humidifier_entity_id,
        sensor_entity_id,
        min_humidity,
        max_humidity,
        target_humidity,
        dry_mode,
        min_cycle_duration,
        dry_tolerance,
        wet_tolerance,
        keep_alive,
        initial_operation_mode,
        away_humidity,
    ):
        """Initialize the hygrostat."""
        self._name = name
        self.humidifier_entity_id = humidifier_entity_id
        self.sensor_entity_id = sensor_entity_id
        self.dry_mode = dry_mode
        self.min_cycle_duration = min_cycle_duration
        self._dry_tolerance = dry_tolerance
        self._wet_tolerance = wet_tolerance
        self._keep_alive = keep_alive
        self._operation_mode = initial_operation_mode
        self._saved_target_humidity = target_humidity or away_humidity
        if self.dry_mode:
            self._operation_list = [OPERATION_MODE_DRY, OPERATION_MODE_OFF]
        else:
            self._operation_list = [OPERATION_MODE_HUMIDIFY, OPERATION_MODE_OFF]
        self._active = False
        self._cur_humidity = None
        self._humidity_lock = asyncio.Lock()
        self._min_humidity = min_humidity
        self._max_humidity = max_humidity
        self._target_humidity = target_humidity
        self._support_flags = SUPPORT_FLAGS
        if away_humidity:
            self._support_flags = SUPPORT_FLAGS | SUPPORT_PRESET_MODE
        self._away_humidity = away_humidity
        self._is_away = False

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        async_track_state_change(
            self.hass, self.sensor_entity_id, self._async_sensor_changed
        )
        async_track_state_change(
            self.hass, self.humidifier_entity_id, self._async_switch_changed
        )

        if self._keep_alive:
            async_track_time_interval(
                self.hass, self._async_control_humidifying, self._keep_alive
            )

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self.sensor_entity_id)
            if sensor_state and sensor_state.state != STATE_UNKNOWN:
                self._async_update_humidity(sensor_state)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        # Check If we have an old state
        old_state = await self.async_get_last_state()
        if old_state is not None:
            # If we have no initial humidity, restore
            if self._target_humidity is None:
                # If we have a previously saved humidity
                if old_state.attributes.get(ATTR_HUMIDITY) is None:
                    if self.dry_mode:
                        self._target_humidity = self.max_humidity
                    else:
                        self._target_humidity = self.min_humidity
                    _LOGGER.warning(
                        "Undefined target humidity," "falling back to %s",
                        self._target_humidity,
                    )
                else:
                    self._target_humidity = float(old_state.attributes[ATTR_HUMIDITY])
            if old_state.attributes.get(ATTR_PRESET_MODE) == PRESET_AWAY:
                self._is_away = True
            if not self._operation_mode and old_state.state:
                self._operation_mode = old_state.state

        else:
            # No previous state, try and restore defaults
            if self._target_humidity is None:
                if self.dry_mode:
                    self._target_humidity = self.max_humidity
                else:
                    self._target_humidity = self.min_humidity
            _LOGGER.warning(
                "No previously saved humidity, setting to %s", self._target_humidity
            )

        # Set default state to off
        if not self._operation_mode:
            self._operation_mode = OPERATION_MODE_OFF

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the hygrostat."""
        return self._name

    @property
    def current_humidity(self):
        """Return the sensor humidity."""
        return self._cur_humidity

    @property
    def operation_mode(self):
        """Return current operation."""
        return self._operation_mode

    @property
    def humidifier_action(self):
        """Return the current running humidifier operation if supported.

        Need to be one of CURRENT_HUMIDIFIER_*.
        """
        if self._operation_mode == OPERATION_MODE_OFF:
            return CURRENT_HUMIDIFIER_OFF
        if not self._is_device_active:
            return CURRENT_HUMIDIFIER_IDLE
        if self.dry_mode:
            return CURRENT_HUMIDIFIER_DRY
        return CURRENT_HUMIDIFIER_HUMIDIFY

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def operation_modes(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, humidity."""
        if self._is_away:
            return PRESET_AWAY
        return None

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        if self._away_humidity:
            return [PRESET_NONE, PRESET_AWAY]
        return None

    async def async_set_operation_mode(self, operation_mode):
        """Set humidifier mode."""
        if operation_mode == OPERATION_MODE_HUMIDIFY:
            self._operation_mode = OPERATION_MODE_HUMIDIFY
            await self._async_control_humidifying(force=True)
        elif operation_mode == OPERATION_MODE_DRY:
            self._operation_mode = OPERATION_MODE_DRY
            await self._async_control_humidifying(force=True)
        elif operation_mode == OPERATION_MODE_OFF:
            self._operation_mode = OPERATION_MODE_OFF
            if self._is_device_active:
                await self._async_humidifier_turn_off()
        else:
            _LOGGER.error("Unrecognized humidifier mode: %s", operation_mode)
            return
        # Ensure we update the current operation after changing the mode
        self.schedule_update_ha_state()

    async def async_set_humidity(self, humidity: int):
        """Set new target humidity."""
        if humidity is None:
            return

        self._target_humidity = humidity
        await self._async_control_humidifying(force=True)
        await self.async_update_ha_state()

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        if self._min_humidity:
            return self._min_humidity

        # get default humidity from super class
        return super().min_humidity

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        if self._max_humidity:
            return self._max_humidity

        # Get default humidity from super class
        return super().max_humidity

    async def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle humidity changes."""
        if new_state is None:
            return

        self._async_update_humidity(new_state)
        await self._async_control_humidifying()
        await self.async_update_ha_state()

    @callback
    def _async_switch_changed(self, entity_id, old_state, new_state):
        """Handle humidifier switch state changes."""
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    @callback
    def _async_update_humidity(self, state):
        """Update hygrostat with latest state from sensor."""
        try:
            self._cur_humidity = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    async def _async_control_humidifying(self, time=None, force=False):
        """Check if we need to turn humidifying on or off."""
        async with self._humidity_lock:
            if not self._active and None not in (
                self._cur_humidity,
                self._target_humidity,
            ):
                self._active = True
                _LOGGER.info(
                    "Obtained current and target humidity. "
                    "Generic hygrostat active. %s, %s",
                    self._cur_humidity,
                    self._target_humidity,
                )

            if not self._active or self._operation_mode == OPERATION_MODE_OFF:
                return

            if not force and time is None:
                # If the `force` argument is True, we
                # ignore `min_cycle_duration`.
                # If the `time` argument is not none, we were invoked for
                # keep-alive purposes, and `min_cycle_duration` is irrelevant.
                if self.min_cycle_duration:
                    if self._is_device_active:
                        current_state = STATE_ON
                    else:
                        current_state = OPERATION_MODE_OFF
                    long_enough = condition.state(
                        self.hass,
                        self.humidifier_entity_id,
                        current_state,
                        self.min_cycle_duration,
                    )
                    if not long_enough:
                        return

            too_dry = self._target_humidity - self._cur_humidity >= self._dry_tolerance
            too_wet = self._cur_humidity - self._target_humidity >= self._wet_tolerance
            if self._is_device_active:
                if (self.dry_mode and too_dry) or (not self.dry_mode and too_wet):
                    _LOGGER.info("Turning off humidifier %s", self.humidifier_entity_id)
                    await self._async_humidifier_turn_off()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    await self._async_humidifier_turn_on()
            else:
                if (self.dry_mode and too_wet) or (not self.dry_mode and too_dry):
                    _LOGGER.info("Turning on humidifier %s", self.humidifier_entity_id)
                    await self._async_humidifier_turn_on()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    await self._async_humidifier_turn_off()

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self.hass.states.is_state(self.humidifier_entity_id, STATE_ON)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    async def _async_humidifier_turn_on(self):
        """Turn humidifier toggleable device on."""
        data = {ATTR_ENTITY_ID: self.humidifier_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)

    async def _async_humidifier_turn_off(self):
        """Turn humidifier toggleable device off."""
        data = {ATTR_ENTITY_ID: self.humidifier_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode.

        This method must be run in the event loop and returns a coroutine.
        """
        if preset_mode == PRESET_AWAY and not self._is_away:
            self._is_away = True
            self._saved_target_humidity = self._target_humidity
            self._target_humidity = self._away_humidity
            await self._async_control_humidifying(force=True)
        elif preset_mode == PRESET_NONE and self._is_away:
            self._is_away = False
            self._target_humidity = self._saved_target_humidity
            await self._async_control_humidifying(force=True)

        await self.async_update_ha_state()
