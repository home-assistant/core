"""Support for Tado thermostats."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import PyTado
import voluptuous as vol

from homeassistant.components.climate import (
    FAN_AUTO,
    PRESET_AWAY,
    PRESET_HOME,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import TadoConfigEntry, TadoConnector
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
    CONST_OVERLAY_TADO_OPTIONS,
    DOMAIN,
    HA_TERMINATION_DURATION,
    HA_TERMINATION_TYPE,
    HA_TO_TADO_FAN_MODE_MAP,
    HA_TO_TADO_FAN_MODE_MAP_LEGACY,
    HA_TO_TADO_HVAC_MODE_MAP,
    ORDERED_KNOWN_TADO_MODES,
    PRESET_AUTO,
    SIGNAL_TADO_UPDATE_RECEIVED,
    SUPPORT_PRESET_AUTO,
    SUPPORT_PRESET_MANUAL,
    TADO_DEFAULT_MAX_TEMP,
    TADO_DEFAULT_MIN_TEMP,
    TADO_FANLEVEL_SETTING,
    TADO_FANSPEED_SETTING,
    TADO_HORIZONTAL_SWING_SETTING,
    TADO_HVAC_ACTION_TO_HA_HVAC_ACTION,
    TADO_MODES_WITH_NO_TEMP_SETTING,
    TADO_SWING_OFF,
    TADO_SWING_ON,
    TADO_SWING_SETTING,
    TADO_TO_HA_FAN_MODE_MAP,
    TADO_TO_HA_FAN_MODE_MAP_LEGACY,
    TADO_TO_HA_HVAC_MODE_MAP,
    TADO_TO_HA_OFFSET_MAP,
    TADO_TO_HA_SWING_MODE_MAP,
    TADO_VERTICAL_SWING_SETTING,
    TEMP_OFFSET,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
)
from .entity import TadoZoneEntity
from .helper import decide_duration, decide_overlay_mode, generate_supported_fanmodes

_LOGGER = logging.getLogger(__name__)

SERVICE_CLIMATE_TIMER = "set_climate_timer"
ATTR_TIME_PERIOD = "time_period"
ATTR_REQUESTED_OVERLAY = "requested_overlay"

CLIMATE_TIMER_SCHEMA: VolDictType = {
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

CLIMATE_TEMP_OFFSET_SCHEMA: VolDictType = {
    vol.Required(ATTR_OFFSET, default=0): vol.Coerce(float),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: TadoConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tado climate platform."""

    tado = entry.runtime_data
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

    async_add_entities(entities, True)


def _generate_entities(tado: TadoConnector) -> list[TadoClimate]:
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


def create_climate_entity(
    tado: TadoConnector, name: str, zone_id: int, device_info: dict
) -> TadoClimate | None:
    """Create a Tado climate entity."""
    capabilities = tado.get_capabilities(zone_id)
    _LOGGER.debug("Capabilities for zone %s: %s", zone_id, capabilities)

    zone_type = capabilities["type"]
    support_flags = (
        ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    supported_hvac_modes = [
        TADO_TO_HA_HVAC_MODE_MAP[CONST_MODE_OFF],
        TADO_TO_HA_HVAC_MODE_MAP[CONST_MODE_SMART_SCHEDULE],
    ]
    supported_fan_modes = None
    supported_swing_modes = None
    heat_temperatures = None
    cool_temperatures = None

    if zone_type == TYPE_AIR_CONDITIONING:
        # Heat is preferred as it generally has a lower minimum temperature
        for mode in ORDERED_KNOWN_TADO_MODES:
            if mode not in capabilities:
                continue

            supported_hvac_modes.append(TADO_TO_HA_HVAC_MODE_MAP[mode])
            if (
                TADO_SWING_SETTING in capabilities[mode]
                or TADO_VERTICAL_SWING_SETTING in capabilities[mode]
                or TADO_VERTICAL_SWING_SETTING in capabilities[mode]
            ):
                support_flags |= ClimateEntityFeature.SWING_MODE
                supported_swing_modes = []
                if TADO_SWING_SETTING in capabilities[mode]:
                    supported_swing_modes.append(
                        TADO_TO_HA_SWING_MODE_MAP[TADO_SWING_ON]
                    )
                if TADO_VERTICAL_SWING_SETTING in capabilities[mode]:
                    supported_swing_modes.append(SWING_VERTICAL)
                if TADO_HORIZONTAL_SWING_SETTING in capabilities[mode]:
                    supported_swing_modes.append(SWING_HORIZONTAL)
                if (
                    SWING_HORIZONTAL in supported_swing_modes
                    and SWING_VERTICAL in supported_swing_modes
                ):
                    supported_swing_modes.append(SWING_BOTH)
                supported_swing_modes.append(TADO_TO_HA_SWING_MODE_MAP[TADO_SWING_OFF])

            if (
                TADO_FANSPEED_SETTING not in capabilities[mode]
                and TADO_FANLEVEL_SETTING not in capabilities[mode]
            ):
                continue

            support_flags |= ClimateEntityFeature.FAN_MODE

            if supported_fan_modes:
                continue

            if TADO_FANSPEED_SETTING in capabilities[mode]:
                supported_fan_modes = generate_supported_fanmodes(
                    TADO_TO_HA_FAN_MODE_MAP_LEGACY,
                    capabilities[mode][TADO_FANSPEED_SETTING],
                )

            else:
                supported_fan_modes = generate_supported_fanmodes(
                    TADO_TO_HA_FAN_MODE_MAP, capabilities[mode][TADO_FANLEVEL_SETTING]
                )

        cool_temperatures = capabilities[CONST_MODE_COOL]["temperatures"]
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

    return TadoClimate(
        tado,
        name,
        zone_id,
        zone_type,
        supported_hvac_modes,
        support_flags,
        device_info,
        heat_min_temp,
        heat_max_temp,
        heat_step,
        cool_min_temp,
        cool_max_temp,
        cool_step,
        supported_fan_modes,
        supported_swing_modes,
    )


class TadoClimate(TadoZoneEntity, ClimateEntity):
    """Representation of a Tado climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_name = None
    _attr_translation_key = DOMAIN
    _available = False

    def __init__(
        self,
        tado: TadoConnector,
        zone_name: str,
        zone_id: int,
        zone_type: str,
        supported_hvac_modes: list[HVACMode],
        support_flags: ClimateEntityFeature,
        device_info: dict[str, str],
        heat_min_temp: float | None = None,
        heat_max_temp: float | None = None,
        heat_step: float | None = None,
        cool_min_temp: float | None = None,
        cool_max_temp: float | None = None,
        cool_step: float | None = None,
        supported_fan_modes: list[str] | None = None,
        supported_swing_modes: list[str] | None = None,
    ) -> None:
        """Initialize of Tado climate entity."""
        self._tado = tado
        super().__init__(zone_name, tado.home_id, zone_id)

        self.zone_id = zone_id
        self.zone_type = zone_type

        self._attr_unique_id = f"{zone_type} {zone_id} {tado.home_id}"

        self._device_info = device_info
        self._device_id = self._device_info["shortSerialNo"]

        self._ac_device = zone_type == TYPE_AIR_CONDITIONING
        self._attr_hvac_modes = supported_hvac_modes
        self._attr_fan_modes = supported_fan_modes
        self._attr_supported_features = support_flags

        self._cur_temp = None
        self._cur_humidity = None
        self._attr_swing_modes = supported_swing_modes

        self._heat_min_temp = heat_min_temp
        self._heat_max_temp = heat_max_temp
        self._heat_step = heat_step

        self._cool_min_temp = cool_min_temp
        self._cool_max_temp = cool_max_temp
        self._cool_step = cool_step

        self._target_temp: float | None = None

        self._current_tado_fan_speed = CONST_FAN_OFF
        self._current_tado_fan_level = CONST_FAN_OFF
        self._current_tado_hvac_mode = CONST_MODE_OFF
        self._current_tado_hvac_action = HVACAction.OFF
        self._current_tado_swing_mode = TADO_SWING_OFF
        self._current_tado_vertical_swing = TADO_SWING_OFF
        self._current_tado_horizontal_swing = TADO_SWING_OFF

        capabilities = tado.get_capabilities(zone_id)
        self._current_tado_capabilities = capabilities

        self._tado_zone_data: PyTado.TadoZone = {}
        self._tado_geofence_data: dict[str, str] | None = None

        self._tado_zone_temp_offset: dict[str, Any] = {}

        self._async_update_home_data()
        self._async_update_zone_data()

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(self._tado.home_id, "home", "data"),
                self._async_update_home_callback,
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_TADO_UPDATE_RECEIVED.format(
                    self._tado.home_id, "zone", self.zone_id
                ),
                self._async_update_zone_callback,
            )
        )

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._tado_zone_data.current_humidity

    @property
    def current_temperature(self) -> float | None:
        """Return the sensor temperature."""
        return self._tado_zone_data.current_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        return TADO_TO_HA_HVAC_MODE_MAP.get(self._current_tado_hvac_mode, HVACMode.OFF)

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        return TADO_HVAC_ACTION_TO_HA_HVAC_ACTION.get(
            self._tado_zone_data.current_hvac_action, HVACAction.OFF
        )

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self._ac_device:
            if self._is_valid_setting_for_hvac_mode(TADO_FANSPEED_SETTING):
                return TADO_TO_HA_FAN_MODE_MAP_LEGACY.get(
                    self._current_tado_fan_speed, FAN_AUTO
                )
            if self._is_valid_setting_for_hvac_mode(TADO_FANLEVEL_SETTING):
                return TADO_TO_HA_FAN_MODE_MAP.get(
                    self._current_tado_fan_level, FAN_AUTO
                )
            return FAN_AUTO
        return None

    def set_fan_mode(self, fan_mode: str) -> None:
        """Turn fan on/off."""
        if self._is_valid_setting_for_hvac_mode(TADO_FANSPEED_SETTING):
            self._control_hvac(fan_mode=HA_TO_TADO_FAN_MODE_MAP_LEGACY[fan_mode])
        elif self._is_valid_setting_for_hvac_mode(TADO_FANLEVEL_SETTING):
            self._control_hvac(fan_mode=HA_TO_TADO_FAN_MODE_MAP[fan_mode])

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode (home, away or auto)."""

        if (
            self._tado_geofence_data is not None
            and "presenceLocked" in self._tado_geofence_data
        ):
            if not self._tado_geofence_data["presenceLocked"]:
                return PRESET_AUTO
        if self._tado_zone_data.is_away:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def preset_modes(self) -> list[str]:
        """Return a list of available preset modes."""
        if self._tado.get_auto_geofencing_supported():
            return SUPPORT_PRESET_AUTO
        return SUPPORT_PRESET_MANUAL

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._tado.set_presence(preset_mode)

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        if self._tado_zone_data.current_hvac_mode == CONST_MODE_COOL:
            return self._cool_step or self._heat_step
        return self._heat_step or self._cool_step

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        # If the target temperature will be None
        # if the device is performing an action
        # that does not affect the temperature or
        # the device is switching states
        return self._tado_zone_data.target_temp or self._tado_zone_data.current_temp

    def set_timer(
        self,
        temperature: float,
        time_period: int | None = None,
        requested_overlay: str | None = None,
    ):
        """Set the timer on the entity, and temperature if supported."""

        self._control_hvac(
            hvac_mode=CONST_MODE_HEAT,
            target_temp=temperature,
            duration=time_period,
            overlay_mode=requested_overlay,
        )

    def set_temp_offset(self, offset: float) -> None:
        """Set offset on the entity."""

        _LOGGER.debug(
            "Setting temperature offset for device %s setting to (%.1f)",
            self._device_id,
            offset,
        )

        self._tado.set_temperature_offset(self._device_id, offset)

    def set_temperature(self, **kwargs: Any) -> None:
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
    def available(self) -> bool:
        """Return if the device is available."""
        return self._tado_zone_data.available

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if (
            self._current_tado_hvac_mode == CONST_MODE_COOL
            and self._cool_min_temp is not None
        ):
            return self._cool_min_temp
        if self._heat_min_temp is not None:
            return self._heat_min_temp

        return TADO_DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if (
            self._current_tado_hvac_mode == CONST_MODE_HEAT
            and self._heat_max_temp is not None
        ):
            return self._heat_max_temp
        if self._heat_max_temp is not None:
            return self._heat_max_temp

        return TADO_DEFAULT_MAX_TEMP

    @property
    def swing_mode(self) -> str | None:
        """Active swing mode for the device."""
        swing_modes_tuple = (
            self._current_tado_swing_mode,
            self._current_tado_vertical_swing,
            self._current_tado_horizontal_swing,
        )
        if swing_modes_tuple == (TADO_SWING_OFF, TADO_SWING_OFF, TADO_SWING_OFF):
            return TADO_TO_HA_SWING_MODE_MAP[TADO_SWING_OFF]
        if swing_modes_tuple == (TADO_SWING_ON, TADO_SWING_OFF, TADO_SWING_OFF):
            return TADO_TO_HA_SWING_MODE_MAP[TADO_SWING_ON]
        if swing_modes_tuple == (TADO_SWING_OFF, TADO_SWING_ON, TADO_SWING_OFF):
            return SWING_VERTICAL
        if swing_modes_tuple == (TADO_SWING_OFF, TADO_SWING_OFF, TADO_SWING_ON):
            return SWING_HORIZONTAL
        if swing_modes_tuple == (TADO_SWING_OFF, TADO_SWING_ON, TADO_SWING_ON):
            return SWING_BOTH

        return TADO_TO_HA_SWING_MODE_MAP[TADO_SWING_OFF]

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return temperature offset."""
        state_attr: dict[str, Any] = self._tado_zone_temp_offset
        state_attr[HA_TERMINATION_TYPE] = (
            self._tado_zone_data.default_overlay_termination_type
        )
        state_attr[HA_TERMINATION_DURATION] = (
            self._tado_zone_data.default_overlay_termination_duration
        )
        return state_attr

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set swing modes for the device."""
        vertical_swing = None
        horizontal_swing = None
        swing = None
        if self._attr_swing_modes is None:
            return
        if swing_mode == SWING_OFF:
            if self._is_valid_setting_for_hvac_mode(TADO_SWING_SETTING):
                swing = TADO_SWING_OFF
            if self._is_valid_setting_for_hvac_mode(TADO_HORIZONTAL_SWING_SETTING):
                horizontal_swing = TADO_SWING_OFF
            if self._is_valid_setting_for_hvac_mode(TADO_VERTICAL_SWING_SETTING):
                vertical_swing = TADO_SWING_OFF
        if swing_mode == SWING_ON:
            swing = TADO_SWING_ON
        if swing_mode == SWING_VERTICAL:
            if self._is_valid_setting_for_hvac_mode(TADO_VERTICAL_SWING_SETTING):
                vertical_swing = TADO_SWING_ON
            if self._is_valid_setting_for_hvac_mode(TADO_HORIZONTAL_SWING_SETTING):
                horizontal_swing = TADO_SWING_OFF
        if swing_mode == SWING_HORIZONTAL:
            if self._is_valid_setting_for_hvac_mode(TADO_VERTICAL_SWING_SETTING):
                vertical_swing = TADO_SWING_OFF
            if self._is_valid_setting_for_hvac_mode(TADO_HORIZONTAL_SWING_SETTING):
                horizontal_swing = TADO_SWING_ON
        if swing_mode == SWING_BOTH:
            if self._is_valid_setting_for_hvac_mode(TADO_VERTICAL_SWING_SETTING):
                vertical_swing = TADO_SWING_ON
            if self._is_valid_setting_for_hvac_mode(TADO_HORIZONTAL_SWING_SETTING):
                horizontal_swing = TADO_SWING_ON

        self._control_hvac(
            swing_mode=swing,
            vertical_swing=vertical_swing,
            horizontal_swing=horizontal_swing,
        )

    @callback
    def _async_update_zone_data(self) -> None:
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

        self._current_tado_hvac_mode = self._tado_zone_data.current_hvac_mode
        self._current_tado_hvac_action = self._tado_zone_data.current_hvac_action

        if self._is_valid_setting_for_hvac_mode(TADO_FANLEVEL_SETTING):
            self._current_tado_fan_level = self._tado_zone_data.current_fan_level
        if self._is_valid_setting_for_hvac_mode(TADO_FANSPEED_SETTING):
            self._current_tado_fan_speed = self._tado_zone_data.current_fan_speed
        if self._is_valid_setting_for_hvac_mode(TADO_SWING_SETTING):
            self._current_tado_swing_mode = self._tado_zone_data.current_swing_mode
        if self._is_valid_setting_for_hvac_mode(TADO_VERTICAL_SWING_SETTING):
            self._current_tado_vertical_swing = (
                self._tado_zone_data.current_vertical_swing_mode
            )
        if self._is_valid_setting_for_hvac_mode(TADO_HORIZONTAL_SWING_SETTING):
            self._current_tado_horizontal_swing = (
                self._tado_zone_data.current_horizontal_swing_mode
            )

    @callback
    def _async_update_zone_callback(self) -> None:
        """Load tado data and update state."""
        self._async_update_zone_data()
        self.async_write_ha_state()

    @callback
    def _async_update_home_data(self) -> None:
        """Load tado geofencing data into zone."""
        self._tado_geofence_data = self._tado.data["geofence"]

    @callback
    def _async_update_home_callback(self) -> None:
        """Load tado data and update state."""
        self._async_update_home_data()
        self.async_write_ha_state()

    def _normalize_target_temp_for_hvac_mode(self) -> None:
        def adjust_temp(min_temp, max_temp) -> float | None:
            if max_temp is not None and self._target_temp > max_temp:
                return max_temp
            if min_temp is not None and self._target_temp < min_temp:
                return min_temp
            return self._target_temp

        # Set a target temperature if we don't have any
        # This can happen when we switch from Off to On
        if self._target_temp is None:
            self._target_temp = self._tado_zone_data.current_temp
        elif self._current_tado_hvac_mode == CONST_MODE_COOL:
            self._target_temp = adjust_temp(self._cool_min_temp, self._cool_max_temp)
        elif self._current_tado_hvac_mode == CONST_MODE_HEAT:
            self._target_temp = adjust_temp(self._heat_min_temp, self._heat_max_temp)

    def _control_hvac(
        self,
        hvac_mode: str | None = None,
        target_temp: float | None = None,
        fan_mode: str | None = None,
        swing_mode: str | None = None,
        duration: int | None = None,
        overlay_mode: str | None = None,
        vertical_swing: str | None = None,
        horizontal_swing: str | None = None,
    ):
        """Send new target temperature to Tado."""
        if hvac_mode:
            self._current_tado_hvac_mode = hvac_mode

        if target_temp:
            self._target_temp = target_temp

        if fan_mode:
            if self._is_valid_setting_for_hvac_mode(TADO_FANSPEED_SETTING):
                self._current_tado_fan_speed = fan_mode
            if self._is_valid_setting_for_hvac_mode(TADO_FANLEVEL_SETTING):
                self._current_tado_fan_level = fan_mode

        if swing_mode:
            self._current_tado_swing_mode = swing_mode

        if vertical_swing:
            self._current_tado_vertical_swing = vertical_swing

        if horizontal_swing:
            self._current_tado_horizontal_swing = horizontal_swing

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

        overlay_mode = decide_overlay_mode(
            tado=self._tado,
            duration=duration,
            overlay_mode=overlay_mode,
            zone_id=self.zone_id,
        )
        duration = decide_duration(
            tado=self._tado,
            duration=duration,
            zone_id=self.zone_id,
            overlay_mode=overlay_mode,
        )
        _LOGGER.debug(
            (
                "Switching to %s for zone %s (%d) with temperature %s °C and duration"
                " %s using overlay %s"
            ),
            self._current_tado_hvac_mode,
            self.zone_name,
            self.zone_id,
            self._target_temp,
            duration,
            overlay_mode,
        )

        temperature_to_send = self._target_temp
        if self._current_tado_hvac_mode in TADO_MODES_WITH_NO_TEMP_SETTING:
            # A temperature cannot be passed with these modes
            temperature_to_send = None

        fan_speed = None
        fan_level = None
        if self.supported_features & ClimateEntityFeature.FAN_MODE:
            if self._is_current_setting_supported_by_current_hvac_mode(
                TADO_FANSPEED_SETTING, self._current_tado_fan_speed
            ):
                fan_speed = self._current_tado_fan_speed
            if self._is_current_setting_supported_by_current_hvac_mode(
                TADO_FANLEVEL_SETTING, self._current_tado_fan_level
            ):
                fan_level = self._current_tado_fan_level

        swing = None
        vertical_swing = None
        horizontal_swing = None
        if (
            self.supported_features & ClimateEntityFeature.SWING_MODE
        ) and self._attr_swing_modes is not None:
            if self._is_current_setting_supported_by_current_hvac_mode(
                TADO_VERTICAL_SWING_SETTING, self._current_tado_vertical_swing
            ):
                vertical_swing = self._current_tado_vertical_swing
            if self._is_current_setting_supported_by_current_hvac_mode(
                TADO_HORIZONTAL_SWING_SETTING, self._current_tado_horizontal_swing
            ):
                horizontal_swing = self._current_tado_horizontal_swing
            if self._is_current_setting_supported_by_current_hvac_mode(
                TADO_SWING_SETTING, self._current_tado_swing_mode
            ):
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
            fan_level=fan_level,  # api defaults to not sending fanLevel if fanSpeend not None
            vertical_swing=vertical_swing,  # api defaults to not sending verticalSwing if swing not None
            horizontal_swing=horizontal_swing,  # api defaults to not sending horizontalSwing if swing not None
        )

    def _is_valid_setting_for_hvac_mode(self, setting: str) -> bool:
        return (
            self._current_tado_capabilities.get(self._current_tado_hvac_mode, {}).get(
                setting
            )
            is not None
        )

    def _is_current_setting_supported_by_current_hvac_mode(
        self, setting: str, current_state: str | None
    ) -> bool:
        if self._is_valid_setting_for_hvac_mode(setting):
            return current_state in self._current_tado_capabilities[
                self._current_tado_hvac_mode
            ].get(setting, [])
        return False
