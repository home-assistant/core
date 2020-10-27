"""Support for eQ-3 Bluetooth Smart thermostats."""
import asyncio
import logging

from bluepy.btle import BTLEException  # pylint: disable=import-error, no-name-in-module
import eq3bt as eq3  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
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
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    CONF_MAC,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)

CONF_SENSOR = "target_sensor"
CONF_SENSOR_CONTROL = "control_by_target_sensor"
CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"
CONF_COLD_TOLERANCE = "cold_tolerance"
CONF_HOT_TOLERANCE = "hot_tolerance"

DEFAULT_TOLERANCE = 0.3
STATE_BOOST = "boost"

ATTR_STATE_WINDOW_OPEN = "window_open"
ATTR_STATE_VALVE = "valve"
ATTR_STATE_LOCKED = "is_locked"
ATTR_STATE_LOW_BAT = "low_battery"
ATTR_STATE_AWAY_END = "away_end"
ATTR_STATE_THERMOSTAT = "thermostat_state"

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
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): vol.Schema({cv.string: DEVICE_SCHEMA})}
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_FLAGS_SENSOR_CONTROL = SUPPORT_TARGET_TEMPERATURE


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the eQ-3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        sensor_entity_id = device_cfg.get(CONF_SENSOR)
        sensor_control = device_cfg.get(CONF_SENSOR_CONTROL)
        min_temp = device_cfg.get(CONF_MIN_TEMP)
        max_temp = device_cfg.get(CONF_MAX_TEMP)
        precision = device_cfg.get(CONF_PRECISION)
        cold_tolerance = device_cfg.get(CONF_COLD_TOLERANCE)
        hot_tolerance = device_cfg.get(CONF_HOT_TOLERANCE)

        devices.append(
            EQ3BTSmartThermostat(
                mac,
                name,
                sensor_entity_id,
                sensor_control,
                min_temp,
                max_temp,
                precision,
                cold_tolerance,
                hot_tolerance,
            )
        )

    async_add_entities(devices, True)


class EQ3BTSmartThermostat(ClimateEntity, RestoreEntity):
    """Representation of an eQ-3 Bluetooth Smart thermostat."""

    def __init__(
        self,
        _mac,
        _name,
        _sensor_entity_id,
        _sensor_control,
        _min_temp,
        _max_temp,
        _precision,
        _cold_tolerance,
        _hot_tolerance,
    ):
        """Initialize the thermostat."""
        # We want to avoid name clash with this module.
        self._name = _name
        self._sensor_entity_id = _sensor_entity_id
        self._sensor_control = _sensor_control
        self._min_temp = _min_temp
        self._max_temp = _max_temp
        self._temp_precision = _precision
        self._cold_tolerance = _cold_tolerance
        self._hot_tolerance = _hot_tolerance
        self._thermostat = eq3.Thermostat(_mac)
        self._cur_temp = None
        self._target_temp = None
        self._hvac_mode = None
        self._active = False
        self._temp_lock = asyncio.Lock()

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
                "%s - Restored previously saved temperature %s",
                self._name,
                self._target_temp,
            )
        else:
            self._target_temp = self.min_temp
            _LOGGER.warning(
                "%s - No previously saved temperature, setting to %s",
                self._name,
                self._target_temp,
            )

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
            self.set_thermostat_mode(eq3.Mode.Closed)

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
                    "%s - Obtained current and target temperature. "
                    "Thermostat active. %s, %s",
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
                    self._thermostat.mode = eq3.Mode.Closed
                else:
                    _LOGGER.warning(
                        "%s - Target sensor became unavailable. ", self._name,
                    )
                return

            too_cold = self._target_temp >= self._cur_temp + self._cold_tolerance
            too_hot = self._cur_temp >= self._target_temp + self._hot_tolerance

            if self._is_device_active and (self._hvac_mode == HVAC_MODE_OFF or too_hot):
                _LOGGER.info("%s - Turning off thermostat", self._name)
                self.set_thermostat_mode(eq3.Mode.Closed)
            elif (
                self._hvac_mode == HVAC_MODE_HEAT
                and not self._is_device_active
                and too_cold
            ):
                _LOGGER.info("%s - Turning on thermostat", self._name)
                self.set_thermostat_mode(eq3.Mode.Open)

    @property
    def _is_device_active(self):
        """If the thermostat currently active."""
        return self._thermostat.mode == eq3.Mode.Open

    @property
    def supported_features(self):
        """Return the list of supported features."""
        if self._sensor_control:
            return SUPPORT_FLAGS_SENSOR_CONTROL

        return SUPPORT_FLAGS

    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self._thermostat.mode >= eq3.Mode.Closed

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

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
        if self._sensor_entity_id:
            """Return the sensor temperature."""
            return self._cur_temp

        """Can not report temperature, so return target_temperature."""
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
        if temperature is None:
            return

        if self._sensor_control:
            self._target_temp = temperature
            await self._async_control_heating()
            self.async_write_ha_state()
            return

        self._thermostat.target_temperature = temperature

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
        Need to be one of CURRENT_HVAC_*."""
        if not self._sensor_control:
            return None

        if self.hvac_mode == HVAC_MODE_OFF:
            return CURRENT_HVAC_OFF

        return EQ_TO_HA_HVAC_ACTION.get(self._thermostat.mode, "unknown")

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
            self.schedule_update_ha_state()
            return

        if self.preset_mode:
            return

        self.set_thermostat_mode(HA_TO_EQ_HVAC[hvac_mode])

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

        No presets are permitted if sensor control is active.
        """
        if self._sensor_control:
            return PRESET_NONE

        return list(HA_TO_EQ_PRESET.keys())

    async def async_set_preset_mode(self, preset_mode: str):
        """No preset change accepted if sensor control is active."""
        if self._sensor_control:
            return

        """Set new preset mode."""
        if preset_mode == PRESET_NONE:
            await self.async_set_hvac_mode(HVAC_MODE_HEAT)

        self.set_thermostat_mode(HA_TO_EQ_PRESET[preset_mode])

    def update(self):
        """Update the data from the thermostat."""

        _LOGGER.debug("%s - Updating thermostat", self._name)
        try:
            self._thermostat.update()
        except BTLEException as ex:
            _LOGGER.warning("%s - Updating the state failed: %s", self._name, ex)

    def set_thermostat_mode(self, mode):
        """Set the thermostat mode."""

        _LOGGER.debug(
            "%s - Setting thermostat mode to %s", self._name, EQ_TO_STRING[mode]
        )
        try:
            self._thermostat.mode = mode
        except BTLEException as ex:
            _LOGGER.warning("%s - Setting the state failed: %s", self._name, ex)
