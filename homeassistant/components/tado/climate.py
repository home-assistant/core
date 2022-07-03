"""Support for Tado thermostats."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    PRESET_AWAY,
    PRESET_HOME,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
    SWING_OFF,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONST_EXCLUSIVE_OVERLAY_GROUP,
    CONST_FAN_AUTO,
    CONST_FAN_OFF,
    CONST_MODE_AUTO,
    CONST_MODE_COOL,
    CONST_MODE_HEAT,
    CONST_MODE_OFF,
    CONST_MODE_SMART_SCHEDULE,
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TADO_OPTIONS,
    CONST_OVERLAY_TIMER,
    CONST_SWING_MODE_VERTICAL,
    CONST_SWING_MODE_HORIZONTAL,
    CONST_LIGHT,
    DATA,
    DOMAIN,
    HA_TERMINATION_DURATION,
    HA_TERMINATION_TYPE,
    HA_TO_TADO_FAN_MODE_MAP,
    HA_TO_TADO_HVAC_MODE_MAP,
    HA_TO_TADO_SWING_MODE_MAP,
    ORDERED_KNOWN_TADO_MODES,
    KNOWN_TADO_SWING_MODES,
    SIGNAL_TADO_UPDATE_RECEIVED,
    SUPPORT_PRESET,
    TADO_HVAC_ACTION_TO_HA_HVAC_ACTION,
    TADO_MODES_WITH_NO_TEMP_SETTING,
    TADO_SWING_OFF,
    TADO_SWING_ON,
    TADO_TO_HA_FAN_MODE_MAP,
    TADO_TO_HA_HVAC_MODE_MAP,
    TADO_TO_HA_OFFSET_MAP,
    TADO_TO_HA_SWING_MODE_MAP,
    TEMP_OFFSET,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
    TADO_HVAC_MODE_FEATURE_MAP,
    CONST_BASE_FEATURES,
    TADO_LIGHT_OFF,
    TADO_MODES_WITH_NO_FAN_SETTING, CONST_MODE_FAN, CONST_FAN_LEVEL_1,
)
from .entity import TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_CLIMATE_TIMER = "set_climate_timer"
ATTR_TIME_PERIOD = "time_period"
ATTR_REQUESTED_OVERLAY = "requested_overlay"

CLIMATE_TIMER_SCHEMA = {
    vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
    vol.Exclusive(ATTR_TIME_PERIOD, CONST_EXCLUSIVE_OVERLAY_GROUP): vol.All(
        cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds()
    ),
    vol.Exclusive(ATTR_REQUESTED_OVERLAY, CONST_EXCLUSIVE_OVERLAY_GROUP): vol.In(
        CONST_OVERLAY_TADO_OPTIONS
    ),
}

SERVICE_TEMP_OFFSET = "set_climate_temperature_offset"
ATTR_OFFSET = "offset"

CLIMATE_TEMP_OFFSET_SCHEMA = {
    vol.Required(ATTR_OFFSET, default=0): vol.Coerce(float),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado climate platform."""

    tado = hass.data[DOMAIN][entry.entry_id][DATA]
    entities = await hass.async_add_executor_job(_generate_entities, tado)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_CLIMATE_TIMER,
        CLIMATE_TIMER_SCHEMA,
        "set_timer",
    )

    platform.async_register_entity_service(
        SERVICE_TEMP_OFFSET,
        CLIMATE_TEMP_OFFSET_SCHEMA,
        "set_temp_offset",
    )

    if entities:
        async_add_entities(entities, True)


def _generate_entities(tado):
    """Create all climate entities."""
    entities = []
    for zone in tado.zones:
        if zone["type"] in [TYPE_HEATING, TYPE_AIR_CONDITIONING]:
            entity = create_climate_entity(
                tado, zone["name"], zone["id"], zone["devices"][0]
            )
            if entity:
                entities.append(entity)
    return entities


def create_climate_entity(tado, name: str, zone_id: int, device_info: dict):
    """Create a Tado climate entity."""
    capabilities = tado.get_capabilities(zone_id)
    _LOGGER.debug("Capabilities for zone %s: %s", zone_id, capabilities)

    zone_type = capabilities["type"]
    supported_hvac_modes = [
        TADO_TO_HA_HVAC_MODE_MAP[CONST_MODE_OFF],
        TADO_TO_HA_HVAC_MODE_MAP[CONST_MODE_SMART_SCHEDULE],
    ]
    supported_swing_modes = None
    supported_fan_modes = None
    supported_light_modes = None
    heat_temperatures = None
    cool_temperatures = None
    hvac_capability_map = {
        CONST_MODE_OFF: {
            "temperatures": None,
            "light_modes": None,
            "fan_speeds": None,
            "swing_modes": None,
            "support_flags": 0,
        },
        CONST_MODE_SMART_SCHEDULE: {
            "temperatures": None,
            "light_modes": None,
            "fan_speeds": None,
            "swing_modes": None,
            "support_flags": ClimateEntityFeature.PRESET_MODE,
        }
    }

    if zone_type == TYPE_AIR_CONDITIONING:
        # Heat is preferred as it generally has a lower minimum temperature
        for mode in ORDERED_KNOWN_TADO_MODES:
            if mode not in capabilities:
                continue

            supported_hvac_modes.append(TADO_TO_HA_HVAC_MODE_MAP[mode])

            hvac_mode_temperatures = None
            hvac_mode_light_modes = None
            hvac_mode_swing_modes = None
            hvac_mode_support_flags = ClimateEntityFeature.PRESET_MODE
            hvac_mode_fan_speeds = None

            if "temperatures" in capabilities[mode]:
                hvac_mode_temperatures = capabilities[mode]["temperatures"]
                hvac_mode_support_flags |= ClimateEntityFeature.TARGET_TEMPERATURE

            if "light" in capabilities[mode]:
                hvac_mode_light_modes = capabilities[mode][CONST_LIGHT]

            if "fanLevel" in capabilities[mode]:
                hvac_mode_fan_speeds = [
                    TADO_TO_HA_FAN_MODE_MAP[speed]
                    for speed in capabilities[mode]["fanLevel"]
                ]
                hvac_mode_support_flags |= ClimateEntityFeature.FAN_MODE

            # Detect HA compatible Swing Modes
            for swing_mode in KNOWN_TADO_SWING_MODES:
                if swing_mode not in capabilities[mode]:
                    continue
                if hvac_mode_swing_modes:
                    hvac_mode_swing_modes.append(TADO_TO_HA_SWING_MODE_MAP[swing_mode])
                    hvac_mode_swing_modes.append(SWING_BOTH)
                    continue
                hvac_mode_support_flags |= ClimateEntityFeature.SWING_MODE
                hvac_mode_swing_modes = [SWING_OFF, TADO_TO_HA_SWING_MODE_MAP[swing_mode]]

            hvac_capability_map.update({
                mode: {
                    "temperatures": hvac_mode_temperatures,
                    "light_modes": hvac_mode_light_modes,
                    "fan_speeds": hvac_mode_fan_speeds,
                    "swing_modes": supported_swing_modes,
                    "support_flags": hvac_mode_support_flags,
                }
            })

            if not supported_swing_modes:
                supported_swing_modes = hvac_mode_swing_modes
            if not supported_fan_modes:
                supported_fan_modes = hvac_mode_fan_speeds
            if not supported_light_modes:
                supported_light_modes = hvac_mode_light_modes

        cool_temperatures = hvac_capability_map[CONST_MODE_COOL]["temperatures"]

    else:
        supported_hvac_modes.append(HVACMode.HEAT)

    if CONST_MODE_HEAT in capabilities:
        heat_temperatures = capabilities[CONST_MODE_HEAT]["temperatures"]

    if heat_temperatures is None and "temperatures" in capabilities:
        heat_temperatures = capabilities["temperatures"]

    if cool_temperatures is None and heat_temperatures is None:
        _LOGGER.debug("Not adding zone %s since it has no temperatures", name)
        return None

    heat_min_temp = None
    heat_max_temp = None
    heat_step = None
    cool_min_temp = None
    cool_max_temp = None
    cool_step = None

    if heat_temperatures is not None:
        heat_min_temp = float(heat_temperatures["celsius"]["min"])
        heat_max_temp = float(heat_temperatures["celsius"]["max"])
        heat_step = heat_temperatures["celsius"].get("step", PRECISION_TENTHS)

    if cool_temperatures is not None:
        cool_min_temp = float(cool_temperatures["celsius"]["min"])
        cool_max_temp = float(cool_temperatures["celsius"]["max"])
        cool_step = cool_temperatures["celsius"].get("step", PRECISION_TENTHS)

    entity = TadoClimate(
        tado,
        name,
        zone_id,
        zone_type,
        heat_min_temp,
        heat_max_temp,
        heat_step,
        cool_min_temp,
        cool_max_temp,
        cool_step,
        supported_hvac_modes,
        device_info,
        hvac_capability_map,
    )
    return entity


class TadoClimate(TadoZoneEntity, ClimateEntity):
    """Representation of a Tado climate entity."""

    def __init__(
        self,
        tado,
        zone_name,
        zone_id,
        zone_type,
        heat_min_temp,
        heat_max_temp,
        heat_step,
        cool_min_temp,
        cool_max_temp,
        cool_step,
        supported_hvac_modes,
        device_info,
        hvac_capability_map,
    ):
        """Initialize of Tado climate entity."""
        self._tado = tado
        super().__init__(zone_name, tado.home_id, zone_id)

        self.zone_id = zone_id
        self.zone_type = zone_type
        self._unique_id = f"{zone_type} {zone_id} {tado.home_id}"
        self._device_info = device_info
        self._device_id = self._device_info["shortSerialNo"]

        self._ac_device = zone_type == TYPE_AIR_CONDITIONING
        self._supported_hvac_modes = supported_hvac_modes
        self._hvac_capability_map = hvac_capability_map

        self._available = False

        self._cur_temp = None
        self._cur_humidity = None

        self._heat_min_temp = heat_min_temp
        self._heat_max_temp = heat_max_temp
        self._heat_step = heat_step

        self._cool_min_temp = cool_min_temp
        self._cool_max_temp = cool_max_temp
        self._cool_step = cool_step

        self._target_temp = None

        self._current_tado_fan_speed = CONST_FAN_OFF
        self._current_tado_hvac_mode = CONST_MODE_OFF
        self._current_tado_hvac_action = HVACAction.OFF

        self._current_tado_swing_mode = TADO_SWING_OFF
        self._current_tado_vertical_swing_mode = TADO_SWING_OFF
        self._current_tado_horizontal_swing_mode = TADO_SWING_OFF

        self._current_tado_light_mode = TADO_LIGHT_OFF

        self._tado_zone_data = None

        self._tado_zone_temp_offset = {}

        self._async_update_zone_data()

        # Debug
        params = {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "device_info": device_info,
            "ac_device": self._ac_device,
            "supported_hvac_modes": supported_hvac_modes,
            "capabilities": hvac_capability_map,
            "heat_min_temp": heat_min_temp,
            "heat_max_temp": heat_max_temp,
            "heat_step": heat_step,
            "cool_min_temp": cool_min_temp,
            "cool_max_temp": cool_max_temp,
            "cool_step": cool_step,
        }

        # Obfuscate fields
        params["device_info"]["serialNo"] = "[REDACTED]"
        params["device_info"]["shortSerialNo"] = "[REDACTED]"
        params["device_info"]["currentFwVersion"] = "[REDACTED]"
        _LOGGER.warning("%s [%s]", self, params)

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "zone", self.zone_id
                ),
                self._async_update_callback,
            )
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        _LOGGER.warning(self._current_capabilities)
        return self._current_capabilities["support_flags"]

    @property
    def name(self):
        """Return the name of the entity."""
        return self.zone_name

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._tado_zone_data.current_humidity

    @property
    def current_temperature(self):
        """Return the sensor temperature."""
        return self._tado_zone_data.current_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return TADO_TO_HA_HVAC_MODE_MAP.get(self._current_tado_hvac_mode, HVACMode.OFF)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return self._supported_hvac_modes

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return TADO_HVAC_ACTION_TO_HA_HVAC_ACTION.get(
            self._tado_zone_data.current_hvac_action, HVACAction.OFF
        )

    @property
    def fan_mode(self):
        """Return the fan setting."""
        if self._ac_device:
            return TADO_TO_HA_FAN_MODE_MAP.get(self._current_tado_fan_speed, FAN_AUTO)
        return None

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._current_capabilities["fan_speeds"]

    def set_fan_mode(self, fan_mode: str):
        """Turn fan on/off."""
        self._control_hvac(fan_mode=HA_TO_TADO_FAN_MODE_MAP[fan_mode])

    @property
    def preset_mode(self):
        """Return the current preset mode (home, away)."""
        if self._tado_zone_data.is_away:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        self._tado.set_presence(preset_mode)

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        if self._tado_zone_data.current_hvac_mode == CONST_MODE_COOL:
            return self._cool_step or self._heat_step
        return self._heat_step or self._cool_step

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        # If the target temperature will be None
        # if the device is performing an action
        # that does not affect the temperature or
        # the device is switching states
        return self._tado_zone_data.target_temp or self._tado_zone_data.current_temp

    def set_timer(self, temperature=None, time_period=None, requested_overlay=None):
        """Set the timer on the entity, and temperature if supported."""

        self._control_hvac(
            hvac_mode=CONST_MODE_HEAT,
            target_temp=temperature,
            duration=time_period,
            overlay_mode=requested_overlay,
        )

    def set_temp_offset(self, offset):
        """Set offset on the entity."""

        _LOGGER.debug(
            "Setting temperature offset for device %s setting to (%d)",
            self._device_id,
            offset,
        )

        self._tado.set_temperature_offset(self._device_id, offset)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        if self._current_tado_hvac_mode not in (
            CONST_MODE_OFF,
            CONST_MODE_AUTO,
            CONST_MODE_SMART_SCHEDULE,
        ):
            self._control_hvac(target_temp=temperature)
            return

        new_hvac_mode = CONST_MODE_COOL if self._ac_device else CONST_MODE_HEAT
        self._control_hvac(target_temp=temperature, hvac_mode=new_hvac_mode)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        self._control_hvac(hvac_mode=HA_TO_TADO_HVAC_MODE_MAP[hvac_mode])

    @property
    def available(self):
        """Return if the device is available."""
        return self._tado_zone_data.available

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if (
            self._current_tado_hvac_mode == CONST_MODE_COOL
            and self._cool_min_temp is not None
        ):
            return self._cool_min_temp
        if self._heat_min_temp is not None:
            return self._heat_min_temp

        return self._cool_min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if (
            self._current_tado_hvac_mode == CONST_MODE_HEAT
            and self._heat_max_temp is not None
        ):
            return self._heat_max_temp
        if self._heat_max_temp is not None:
            return self._heat_max_temp

        return self._heat_max_temp

    @property
    def swing_mode(self):
        """Active swing mode for the device."""
        if self._current_tado_horizontal_swing_mode == TADO_SWING_ON:
            if self._current_tado_vertical_swing_mode == TADO_SWING_ON:
                return SWING_BOTH
            else:
                return SWING_HORIZONTAL
        elif self._current_tado_vertical_swing_mode == TADO_SWING_ON:
            return SWING_VERTICAL

        return SWING_OFF

    @property
    def swing_modes(self):
        """Swing modes for the device."""
        if self._current_capabilities["support_flags"] & ClimateEntityFeature.SWING_MODE:
            return self._current_capabilities["swing_modes"]
        return None

    @property
    def extra_state_attributes(self):
        """Return temperature offset."""
        state_attr = self._tado_zone_temp_offset
        state_attr[
            HA_TERMINATION_TYPE
        ] = self._tado_zone_data.default_overlay_termination_type
        state_attr[
            HA_TERMINATION_DURATION
        ] = self._tado_zone_data.default_overlay_termination_duration
        state_attr[CONST_LIGHT] = self._current_tado_light_mode
        return state_attr

    def set_swing_mode(self, swing_mode):
        """Set swing modes for the device."""
        if swing_mode in HA_TO_TADO_SWING_MODE_MAP:
            vertical_swing = HA_TO_TADO_SWING_MODE_MAP[swing_mode][CONST_SWING_MODE_VERTICAL]
            horizontal_swing = HA_TO_TADO_SWING_MODE_MAP[swing_mode][CONST_SWING_MODE_HORIZONTAL]
            self._control_hvac(vertical_swing=vertical_swing, horizontal_swing=horizontal_swing)
        else:
            _LOGGER.warning("Tried setting an unsupported swing_mode: %s", swing_mode)

    @callback
    def _async_update_zone_data(self):
        """Load tado data into zone."""
        self._tado_zone_data = self._tado.data["zone"][self.zone_id]

        # Assign offset values to mapped attributes
        for offset_key, attr in TADO_TO_HA_OFFSET_MAP.items():
            if (
                self._device_id in self._tado.data["device"]
                and offset_key
                in self._tado.data["device"][self._device_id][TEMP_OFFSET]
            ):
                self._tado_zone_temp_offset[attr] = self._tado.data["device"][
                    self._device_id
                ][TEMP_OFFSET][offset_key]
        self._current_tado_fan_speed = self._tado_zone_data.current_fan_speed
        self._current_tado_hvac_mode = self._tado_zone_data.current_hvac_mode
        self._current_tado_hvac_action = self._tado_zone_data.current_hvac_action
        self._current_tado_swing_mode = self._tado_zone_data.current_swing_mode
        self._current_tado_vertical_swing_mode = self._tado_zone_data.current_vertical_swing_mode
        self._current_tado_horizontal_swing_mode = self._tado_zone_data.current_horizontal_swing_mode
        self._current_tado_light_mode = self._tado_zone_data.current_light_mode

    @callback
    def _async_update_callback(self):
        """Load tado data and update state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    def _normalize_target_temp_for_hvac_mode(self):
        # Set a target temperature if we don't have any
        # This can happen when we switch from Off to On
        if self._target_temp is None:
            self._target_temp = self._tado_zone_data.target_temp or self._tado_zone_data.current_temp
        elif self._current_tado_hvac_mode == CONST_MODE_COOL:
            if self._target_temp > self._cool_max_temp:
                self._target_temp = self._cool_max_temp
            elif self._target_temp < self._cool_min_temp:
                self._target_temp = self._cool_min_temp
        elif self._current_tado_hvac_mode == CONST_MODE_HEAT:
            if self._target_temp > self._heat_max_temp:
                self._target_temp = self._heat_max_temp
            elif self._target_temp < self._heat_min_temp:
                self._target_temp = self._heat_min_temp

    @property
    def _current_capabilities(self):
        return self._hvac_capability_map[self._current_tado_hvac_mode]

    def _control_hvac(
        self,
        hvac_mode=None,
        target_temp=None,
        fan_mode=None,
        vertical_swing=None,
        horizontal_swing=None,
        duration=None,
        overlay_mode=None,
    ):
        """Send new target temperature to Tado."""

        if hvac_mode:
            self._current_tado_hvac_mode = hvac_mode

        if target_temp:
            self._target_temp = target_temp

        if fan_mode:
            self._current_tado_fan_speed = fan_mode

        if horizontal_swing:
            self._current_tado_horizontal_swing_mode = horizontal_swing

        if vertical_swing:
            self._current_tado_horizontal_swing_mode = vertical_swing

        self._normalize_target_temp_for_hvac_mode()

        # tado does not permit setting the fan speed to
        # off, you must turn off the device
        if (
            self._current_tado_fan_speed == CONST_FAN_OFF
            and self._current_tado_hvac_mode != CONST_MODE_OFF
        ):
            self._current_tado_fan_speed = CONST_FAN_AUTO

        if self._current_tado_hvac_mode == CONST_MODE_OFF:
            _LOGGER.debug(
                "Switching to OFF for zone %s (%d)", self.zone_name, self.zone_id
            )
            self._tado.set_zone_off(self.zone_id, CONST_OVERLAY_MANUAL, self.zone_type)
            return

        if self._current_tado_hvac_mode == CONST_MODE_SMART_SCHEDULE:
            _LOGGER.debug(
                "Switching to SMART_SCHEDULE for zone %s (%d)",
                self.zone_name,
                self.zone_id,
            )
            self._tado.reset_zone_overlay(self.zone_id)
            return

        # If user gave duration then overlay mode needs to be timer
        if duration:
            overlay_mode = CONST_OVERLAY_TIMER
        # If no duration or timer set to fallback setting
        if overlay_mode is None:
            overlay_mode = (
                self._tado.fallback
                if self._tado.fallback is not None
                else CONST_OVERLAY_TADO_MODE
            )
        # If default is Tado default then look it up
        if overlay_mode == CONST_OVERLAY_TADO_DEFAULT:
            overlay_mode = (
                self._tado_zone_data.default_overlay_termination_type
                if self._tado_zone_data.default_overlay_termination_type is not None
                else CONST_OVERLAY_TADO_MODE
            )
        # If we ended up with a timer but no duration, set a default duration
        if overlay_mode == CONST_OVERLAY_TIMER and duration is None:
            duration = (
                self._tado_zone_data.default_overlay_termination_duration
                if self._tado_zone_data.default_overlay_termination_duration is not None
                else "3600"
            )

        _LOGGER.debug(
            "Switching to %s for zone %s (%d) with temperature %s °C and duration %s using overlay %s",
            self._current_tado_hvac_mode,
            self.zone_name,
            self.zone_id,
            self._target_temp,
            duration,
            overlay_mode,
        )

        horizontal_swing = None
        vertical_swing = None
        light_mode = None
        fan_speed_to_send = None
        temperature_to_send = self._target_temp

        if self._current_capabilities["support_flags"] & ClimateEntityFeature.FAN_MODE:
            fan_speed_to_send = self._current_tado_fan_speed

        if self._current_capabilities["support_flags"] & ClimateEntityFeature.SWING_MODE:
            if SWING_VERTICAL in self._current_capabilities["swing_modes"]:
                vertical_swing = self._current_tado_vertical_swing_mode or TADO_SWING_OFF
            if SWING_HORIZONTAL in self._current_capabilities["swing_modes"]:
                horizontal_swing = self._current_tado_horizontal_swing_mode or TADO_SWING_OFF

        # Tado will refuse any HVAC changes if a "light" mode is listed as a
        # capability but not provided with every HVAC change
        # Todo: Allow light mode to be adjusted by the end user.
        if self._current_capabilities["light_modes"]:
            light_mode = self._current_tado_light_mode or self._current_capabilities["light_modes"][0]

        # Tado only accepts certain settings in some HVAC modes.
        # Here we reset any forbidden settings so our requests won't be rejected.
        if not self._current_capabilities["support_flags"] & ClimateEntityFeature.TARGET_TEMPERATURE:
            temperature_to_send = None
        if not self._current_capabilities["support_flags"] & ClimateEntityFeature.FAN_MODE:
            fan_speed_to_send = None
        if fan_speed_to_send not in self._current_capabilities["fan_speeds"]:
            fan_speed_to_send = self._current_capabilities["fan_speeds"][0]

        self._tado.set_zone_overlay(
            zone_id=self.zone_id,
            overlay_mode=overlay_mode,  # What to do when the period ends
            temperature=temperature_to_send,
            duration=duration,
            device_type=self.zone_type,
            mode=self._current_tado_hvac_mode,
            fan_speed=fan_speed_to_send,
            horizontal_swing=horizontal_swing,
            vertical_swing=vertical_swing,
            light=light_mode,
        )
