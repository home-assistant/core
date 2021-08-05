"""Support for Tado thermostats."""
import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONST_FAN_AUTO,
    CONST_FAN_OFF,
    CONST_MODE_AUTO,
    CONST_MODE_COOL,
    CONST_MODE_HEAT,
    CONST_MODE_OFF,
    CONST_MODE_SMART_SCHEDULE,
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TIMER,
    DATA,
    DOMAIN,
    HA_TO_TADO_FAN_MODE_MAP,
    HA_TO_TADO_HVAC_MODE_MAP,
    ORDERED_KNOWN_TADO_MODES,
    SIGNAL_TADO_UPDATE_RECEIVED,
    SUPPORT_PRESET,
    TADO_HVAC_ACTION_TO_HA_HVAC_ACTION,
    TADO_MODES_WITH_NO_TEMP_SETTING,
    TADO_SWING_OFF,
    TADO_SWING_ON,
    TADO_TO_HA_FAN_MODE_MAP,
    TADO_TO_HA_HVAC_MODE_MAP,
    TADO_TO_HA_OFFSET_MAP,
    TEMP_OFFSET,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
)
from .entity import TadoZoneEntity

_LOGGER = logging.getLogger(__name__)

SERVICE_CLIMATE_TIMER = "set_climate_timer"
ATTR_TIME_PERIOD = "time_period"

CLIMATE_TIMER_SCHEMA = {
    vol.Required(ATTR_TIME_PERIOD, default="01:00:00"): vol.All(
        cv.time_period, cv.positive_timedelta, lambda td: td.total_seconds()
    ),
    vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
}

SERVICE_TEMP_OFFSET = "set_climate_temperature_offset"
ATTR_OFFSET = "offset"

CLIMATE_TEMP_OFFSET_SCHEMA = {
    vol.Required(ATTR_OFFSET, default=0): vol.Coerce(float),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
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
    support_flags = SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
    supported_hvac_modes = [
        TADO_TO_HA_HVAC_MODE_MAP[CONST_MODE_OFF],
        TADO_TO_HA_HVAC_MODE_MAP[CONST_MODE_SMART_SCHEDULE],
    ]
    supported_fan_modes = None
    heat_temperatures = None
    cool_temperatures = None

    if zone_type == TYPE_AIR_CONDITIONING:
        # Heat is preferred as it generally has a lower minimum temperature
        for mode in ORDERED_KNOWN_TADO_MODES:
            if mode not in capabilities:
                continue

            supported_hvac_modes.append(TADO_TO_HA_HVAC_MODE_MAP[mode])
            if capabilities[mode].get("swings"):
                support_flags |= SUPPORT_SWING_MODE

            if not capabilities[mode].get("fanSpeeds"):
                continue

            support_flags |= SUPPORT_FAN_MODE

            if supported_fan_modes:
                continue

            supported_fan_modes = [
                TADO_TO_HA_FAN_MODE_MAP[speed]
                for speed in capabilities[mode]["fanSpeeds"]
            ]

        cool_temperatures = capabilities[CONST_MODE_COOL]["temperatures"]
    else:
        supported_hvac_modes.append(HVAC_MODE_HEAT)

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
        supported_fan_modes,
        support_flags,
        device_info,
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
        supported_fan_modes,
        support_flags,
        device_info,
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
        self._supported_fan_modes = supported_fan_modes
        self._support_flags = support_flags

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
        self._current_tado_hvac_action = CURRENT_HVAC_OFF
        self._current_tado_swing_mode = TADO_SWING_OFF

        self._tado_zone_data = None

        self._tado_zone_temp_offset = {}

        self._async_update_zone_data()

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
        return self._support_flags

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
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return TADO_TO_HA_HVAC_MODE_MAP.get(self._current_tado_hvac_mode, HVAC_MODE_OFF)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return self._supported_hvac_modes

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return TADO_HVAC_ACTION_TO_HA_HVAC_ACTION.get(
            self._tado_zone_data.current_hvac_action, CURRENT_HVAC_OFF
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
        return self._supported_fan_modes

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

    def set_timer(self, time_period, temperature=None):
        """Set the timer on the entity, and temperature if supported."""

        self._control_hvac(
            hvac_mode=CONST_MODE_HEAT, target_temp=temperature, duration=time_period
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
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
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

    def set_hvac_mode(self, hvac_mode):
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
        return self._current_tado_swing_mode

    @property
    def swing_modes(self):
        """Swing modes for the device."""
        if self._support_flags & SUPPORT_SWING_MODE:
            return [TADO_SWING_ON, TADO_SWING_OFF]
        return None

    @property
    def extra_state_attributes(self):
        """Return temperature offset."""
        return self._tado_zone_temp_offset

    def set_swing_mode(self, swing_mode):
        """Set swing modes for the device."""
        self._control_hvac(swing_mode=swing_mode)

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

    @callback
    def _async_update_callback(self):
        """Load tado data and update state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    def _normalize_target_temp_for_hvac_mode(self):
        # Set a target temperature if we don't have any
        # This can happen when we switch from Off to On
        if self._target_temp is None:
            self._target_temp = self._tado_zone_data.current_temp
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

    def _control_hvac(
        self,
        hvac_mode=None,
        target_temp=None,
        fan_mode=None,
        swing_mode=None,
        duration=None,
    ):
        """Send new target temperature to Tado."""

        if hvac_mode:
            self._current_tado_hvac_mode = hvac_mode

        if target_temp:
            self._target_temp = target_temp

        if fan_mode:
            self._current_tado_fan_speed = fan_mode

        if swing_mode:
            self._current_tado_swing_mode = swing_mode

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

        _LOGGER.debug(
            "Switching to %s for zone %s (%d) with temperature %s °C and duration %s",
            self._current_tado_hvac_mode,
            self.zone_name,
            self.zone_id,
            self._target_temp,
            duration,
        )

        overlay_mode = CONST_OVERLAY_MANUAL
        if duration:
            overlay_mode = CONST_OVERLAY_TIMER
        elif self._tado.fallback:
            # Fallback to Smart Schedule at next Schedule switch if we have fallback enabled
            overlay_mode = CONST_OVERLAY_TADO_MODE

        temperature_to_send = self._target_temp
        if self._current_tado_hvac_mode in TADO_MODES_WITH_NO_TEMP_SETTING:
            # A temperature cannot be passed with these modes
            temperature_to_send = None

        fan_speed = None
        if self._support_flags & SUPPORT_FAN_MODE:
            fan_speed = self._current_tado_fan_speed
        swing = None
        if self._support_flags & SUPPORT_SWING_MODE:
            swing = self._current_tado_swing_mode

        self._tado.set_zone_overlay(
            zone_id=self.zone_id,
            overlay_mode=overlay_mode,  # What to do when the period ends
            temperature=temperature_to_send,
            duration=duration,
            device_type=self.zone_type,
            mode=self._current_tado_hvac_mode,
            fan_speed=fan_speed,  # api defaults to not sending fanSpeed if None specified
            swing=swing,  # api defaults to not sending swing if None specified
        )
