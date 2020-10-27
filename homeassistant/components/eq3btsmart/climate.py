"""Support for eQ-3 Bluetooth Smart thermostats."""
import asyncio
from datetime import datetime
import logging
from typing import Optional

from bluepy.btle import BTLEException  # pylint: disable=import-error, no-name-in-module
import eq3bt as eq3  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    CONF_MAC,
    CONF_UNIQUE_ID,
    EVENT_HOMEASSISTANT_START,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.dt import utcnow

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_SENSOR = "target_sensor"
CONF_SENSOR_CONTROL = "control_by_target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"
CONF_OFF_TEMP_OFFSET = "off_temp_offset"
CONF_ON_TEMP_OFFSET = "on_temp_offset"

DEFAULT_TOLERANCE = 0.3
STATE_BOOST = "boost"

ATTR_STATE_WINDOW_OPEN = "window_open"
ATTR_STATE_VALVE = "valve"
ATTR_STATE_LOCKED = "is_locked"
ATTR_STATE_LOW_BAT = "low_battery"
ATTR_STATE_AWAY_END = "away_end"
ATTR_STATE_THERMOSTAT = "thermostat_state"
ATTR_STATE_ERROR = "error"
ATTR_STATE_LAST_ERROR_AT = "last_error_at"

EQ_TO_HA_HVAC = {
    eq3.Mode.Closed: HVAC_MODE_OFF,
    eq3.Mode.Open: HVAC_MODE_HEAT,
    eq3.Mode.Auto: HVAC_MODE_AUTO,
    eq3.Mode.Manual: HVAC_MODE_HEAT,
    eq3.Mode.Away: HVAC_MODE_HEAT,
    eq3.Mode.Boost: HVAC_MODE_AUTO,
}

HA_TO_EQ_HVAC = {
    HVAC_MODE_OFF: eq3.Mode.Closed,
    HVAC_MODE_HEAT: eq3.Mode.Manual,
    HVAC_MODE_AUTO: eq3.Mode.Auto,
}
HA_TO_EQ_HVAC_SENSOR_CONTROL = {
    HVAC_MODE_OFF: eq3.Mode.Closed,
    HVAC_MODE_HEAT: eq3.Mode.Open,
}

EQ_TO_HA_PRESET = {eq3.Mode.Boost: PRESET_BOOST, eq3.Mode.Away: PRESET_AWAY}

HA_TO_EQ_PRESET = {PRESET_BOOST: eq3.Mode.Boost, PRESET_AWAY: eq3.Mode.Away}

EQ_TO_STRING = {
    eq3.Mode.Unknown: "unknown",
    eq3.Mode.Closed: "closed",
    eq3.Mode.Open: "open",
    eq3.Mode.Auto: "auto",
    eq3.Mode.Manual: "manual",
    eq3.Mode.Away: "away",
    eq3.Mode.Boost: "boost",
}

EQ_TO_HA_HVAC_ACTION = {
    eq3.Mode.Open: CURRENT_HVAC_HEAT,
    eq3.Mode.Closed: CURRENT_HVAC_IDLE,
}

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_SENSOR): cv.entity_id,
        vol.Optional(CONF_SENSOR_CONTROL, default=False): cv.boolean,
        vol.Optional(CONF_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_COLD_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_HOT_TOLERANCE, default=DEFAULT_TOLERANCE): vol.Coerce(float),
        vol.Optional(CONF_OFF_TEMP_OFFSET): vol.Coerce(float),
        vol.Optional(CONF_ON_TEMP_OFFSET): vol.Coerce(float),
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): vol.Schema({cv.string: DEVICE_SCHEMA})}
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_FLAGS_SENSOR_CONTROL = SUPPORT_TARGET_TEMPERATURE


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the eQ-3 BLE thermostats."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        devices.append(EQ3BTSmartThermostat(hass, name, device_cfg))

    async_add_entities(devices, True)


class EQ3BTSmartThermostat(ClimateEntity, RestoreEntity):
    """Representation of an eQ-3 Bluetooth Smart thermostat."""

    def __init__(self, hass, _name, device_cfg):
        """Initialize the thermostat."""
        # We want to avoid name clash with this module.

        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, _name, hass=hass)
        self._name = device_cfg.get(ATTR_FRIENDLY_NAME, _name)
        self._unique_id = device_cfg.get(
            CONF_UNIQUE_ID, self.entity_id + "_" + device_cfg[CONF_MAC]
        )
        self._thermostat = eq3.Thermostat(device_cfg[CONF_MAC])

        self._sensor_entity_id = device_cfg.get(CONF_SENSOR)
        self._sensor_control = device_cfg.get(CONF_SENSOR_CONTROL)
        self._min_temp = device_cfg.get(CONF_MIN_TEMP)
        self._max_temp = device_cfg.get(CONF_MAX_TEMP)
        self._temp_precision = device_cfg.get(CONF_PRECISION)
        self._cold_tolerance = device_cfg.get(CONF_COLD_TOLERANCE)
        self._hot_tolerance = device_cfg.get(CONF_HOT_TOLERANCE)
        self._off_temp_offset = device_cfg.get(CONF_OFF_TEMP_OFFSET)
        self._on_temp_offset = device_cfg.get(CONF_ON_TEMP_OFFSET)

        self._cur_temp = None
        self._target_temp = None
        self._off_temp = None
        self._on_temp = None
        self._hvac_mode = None
        self._active = False
        self._temp_lock = asyncio.Lock()
        self._error: Optional[str] = None
        self._last_error_at: Optional[datetime] = None

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        if not self._sensor_entity_id:
            return

        # Add listener
        async_track_state_change(
            self.hass, self._sensor_entity_id, self._async_sensor_changed
        )

        @callback
        def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self._sensor_entity_id)
            if sensor_state and sensor_state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._async_update_temp(sensor_state)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        if not self._sensor_control:
            return

        # If target sensor controls the thermostat we try to restore the old state
        old_state = await self.async_get_last_state()
        if (
            old_state is not None
            and old_state.attributes.get(ATTR_TEMPERATURE) is not None
        ):
            # If we have a previously saved temperature
            self._target_temp = float(old_state.attributes[ATTR_TEMPERATURE])
            _LOGGER.info(
                "%s - Restored previously saved target temperature %s",
                self._name,
                self._target_temp,
            )
        else:
            self._target_temp = self.min_temp
            _LOGGER.warning(
                "%s - No previously saved target temperature, setting to %s",
                self._name,
                self._target_temp,
            )
        self.update_control_temps()

        if old_state is None or old_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # Set default state to off
            self._hvac_mode = HVAC_MODE_OFF
            _LOGGER.warning(
                "%s - No previously state, setting to %s", self._name, self._hvac_mode
            )
        else:
            self._hvac_mode = old_state.state
            _LOGGER.info(
                "%s - Restored previous state, setting to %s",
                self._name,
                self._hvac_mode,
            )

        # Turn thermostat off on start if HVAC_MODE is off to get in sync (it's possible that while HA was off the EQ3 state was changed by other means)
        if self._hvac_mode == HVAC_MODE_OFF or self._cur_temp is None:
            self.turn_off()

    async def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        self._async_update_temp(new_state)
        await self._async_control_heating()
        self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._cur_temp = None
            return

        try:
            self._cur_temp = float(state.state)
        except ValueError as ex:
            _LOGGER.error("%s - Unable to update from sensor: %s", self._name, ex)

    async def _async_control_heating(self):
        """Check if we need to turn heating on or off."""
        if not self._sensor_control:
            return

        async with self._temp_lock:
            if not self._active and None not in (self._cur_temp, self._target_temp):
                self._active = True
                _LOGGER.info(
                    "%s - Obtained current (%s) and target temperature (%s). "
                    "Thermostat active",
                    self._name,
                    self._cur_temp,
                    self._target_temp,
                )

            if not self._active:
                return

            if self._cur_temp is None:
                self._active = False
                if self._is_device_active:
                    _LOGGER.warning(
                        "%s - Target sensor became unavailable. "
                        "Turning off thermostat until it comes back online",
                        self._name,
                    )
                    self.turn_off()
                else:
                    _LOGGER.warning(
                        "%s - Target sensor became unavailable. ",
                        self._name,
                    )
                return

            too_cold = self._target_temp >= self._cur_temp + self._cold_tolerance
            too_hot = self._cur_temp >= self._target_temp + self._hot_tolerance

            if self._is_device_active and (self._hvac_mode == HVAC_MODE_OFF or too_hot):
                self.turn_off()
            elif (
                self._hvac_mode == HVAC_MODE_HEAT
                and not self._is_device_active
                and too_cold
            ):
                self.turn_on()

    @property
    def _is_device_active(self):
        """If the thermostat currently active."""
        return self._thermostat.mode == eq3.Mode.Open or (
            self._thermostat.mode == eq3.Mode.Manual
            and self._thermostat.target_temperature == self._on_temp
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._sensor_control:
            return SUPPORT_FLAGS_SENSOR_CONTROL

        return SUPPORT_FLAGS

    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self._thermostat.mode != eq3.Mode.Unknown

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._temp_precision is not None:
            return self._temp_precision

        return super().precision

    @property
    def current_temperature(self):
        """Return the sensor temperature if defined, otherwise return target_temperature."""
        if self._sensor_entity_id:
            return self._cur_temp

        return self.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._sensor_control:
            return self._target_temp

        return self._thermostat.target_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)

        if temperature is not None:
            if self._sensor_control:
                self._target_temp = temperature
                await self._async_control_heating()
                self.async_write_ha_state()
                self.update_control_temps()
            else:
                self._thermostat.target_temperature = temperature

        if hvac_mode is not None:
            await self.async_set_hvac_mode(hvac_mode)

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        if self._sensor_control:
            return self._hvac_mode

        if self._thermostat.mode < 0:
            return HVAC_MODE_OFF
        return EQ_TO_HA_HVAC[self._thermostat.mode]

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if not self._sensor_control:
            return None

        if self.hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF

        if self._thermostat.mode == eq3.Mode.Manual:
            return CURRENT_HVAC_HEAT if self._is_device_active else CURRENT_HVAC_IDLE

        return EQ_TO_HA_HVAC_ACTION.get(self._thermostat.mode, "-")

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        if self._sensor_control:
            return list(HA_TO_EQ_HVAC_SENSOR_CONTROL.keys())

        return list(HA_TO_EQ_HVAC.keys())

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        if self._sensor_control:
            if hvac_mode not in (HVAC_MODE_HEAT, HVAC_MODE_OFF):
                _LOGGER.error("%s - Unrecognized hvac mode: %s", self._name, hvac_mode)
                return

            _LOGGER.debug("%s - Setting HVAC state to %s", self._name, hvac_mode)
            self._hvac_mode = hvac_mode
            await self._async_control_heating()
            self.async_write_ha_state()
            return

        if self.preset_mode:
            return

        self.set_device_mode(HA_TO_EQ_HVAC[hvac_mode])

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp is not None:
            return self._min_temp

        return self._thermostat.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp is not None:
            return self._max_temp

        return self._thermostat.max_temp

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        dev_specific = {
            ATTR_STATE_AWAY_END: self._thermostat.away_end,
            ATTR_STATE_LOCKED: self._thermostat.locked,
            ATTR_STATE_LOW_BAT: self._thermostat.low_battery,
            ATTR_STATE_VALVE: self._thermostat.valve_state,
            ATTR_STATE_WINDOW_OPEN: self._thermostat.window_open,
            ATTR_STATE_ERROR: self._error,
            ATTR_STATE_LAST_ERROR_AT: self._last_error_at,
        }
        if self._sensor_control:
            dev_specific[ATTR_STATE_THERMOSTAT] = EQ_TO_STRING[self._thermostat.mode]

        return dev_specific

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        return EQ_TO_HA_PRESET.get(self._thermostat.mode)

    @property
    def preset_modes(self):
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        if self._sensor_control:
            return PRESET_NONE

        return list(HA_TO_EQ_PRESET.keys())

    async def async_set_preset_mode(self, preset_mode: str):
        """Set new preset mode."""
        if self._sensor_control:
            return

        if preset_mode == PRESET_NONE:
            await self.async_set_hvac_mode(HVAC_MODE_HEAT)

        self.set_device_mode(HA_TO_EQ_PRESET[preset_mode])

    def update(self):
        """Update the data from the thermostat."""

        _LOGGER.debug("%s - Updating thermostat", self._name)
        try:
            self._thermostat.update()
            self.set_error(None)
        except BTLEException as ex:
            self.set_error(ex)
            _LOGGER.warning("%s - Updating the state failed: %s", self._name, ex)

    def set_device_mode(self, mode):
        """Set the thermostat mode."""

        _LOGGER.debug(
            "%s - Setting thermostat mode to %s", self._name, EQ_TO_STRING[mode]
        )
        try:
            self._thermostat.mode = mode
            self.set_error(None)
        except BTLEException as ex:
            self.set_error(ex)
            _LOGGER.warning("%s - Setting the state failed: %s", self._name, ex)

    def turn_off(self):
        """Turn off thermostat based on the off_temp value."""

        _LOGGER.info("%s - Turning off thermostat", self._name)

        if self._off_temp is None or self._hvac_mode == HVAC_MODE_OFF:
            self.set_device_mode(eq3.Mode.Closed)
        else:
            self.set_device_mode(eq3.Mode.Manual)
            self._thermostat.target_temperature = self._off_temp

    def turn_on(self):
        """Turn on thermostat based on the on_temp value."""

        if self._hvac_mode == HVAC_MODE_OFF:
            _LOGGER.error("%s - Invalid turn on request", self._name)
            return

        _LOGGER.info("%s - Turning on thermostat", self._name)

        if self._on_temp is None:
            self.set_device_mode(eq3.Mode.Open)
        else:
            self.set_device_mode(eq3.Mode.Manual)
            self._thermostat.target_temperature = self._on_temp

    def update_control_temps(self):
        """Update the off_temp and _on_temp."""

        if self._off_temp_offset is not None:
            self._off_temp = self._target_temp - self._off_temp_offset

            if self._off_temp < self._thermostat.min_temp:
                self._off_temp = self._thermostat.min_temp
            elif self._off_temp > self._thermostat.max_temp:
                self._off_temp = self._thermostat.max_temp

            _LOGGER.debug("%s - Setting off_temp to %s", self._name, self._off_temp)
        else:
            self._off_temp = None

        if self._on_temp_offset is not None:
            self._on_temp = self._target_temp + self._on_temp_offset

            if self._on_temp < self._thermostat.min_temp:
                self._on_temp = self._thermostat.min_temp
            elif self._on_temp > self._thermostat.max_temp:
                self._on_temp = self._thermostat.max_temp

            _LOGGER.debug("%s - Setting on_temp to %s", self._name, self._on_temp)
        else:
            self._on_temp = None

    def set_error(self, exc):
        """Set error attributes."""

        if exc:
            self._error = str(exc)
            self._last_error_at = utcnow()
        else:
            self._error = None
