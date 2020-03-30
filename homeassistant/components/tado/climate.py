"""Support for Tado thermostats."""
import logging

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_TADO_UPDATE_RECEIVED
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
    DATA,
    HA_TO_TADO_FAN_MODE_MAP,
    HA_TO_TADO_HVAC_MODE_MAP,
    ORDERED_KNOWN_TADO_MODES,
    SUPPORT_PRESET,
    TADO_HVAC_ACTION_TO_HA_HVAC_ACTION,
    TADO_MODES_WITH_NO_TEMP_SETTING,
    TADO_TO_HA_FAN_MODE_MAP,
    TADO_TO_HA_HVAC_MODE_MAP,
    TYPE_AIR_CONDITIONING,
    TYPE_HEATING,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Tado climate platform."""
    if discovery_info is None:
        return

    api_list = hass.data[DOMAIN][DATA]
    entities = []

    for tado in api_list:
        for zone in tado.zones:
            if zone["type"] in [TYPE_HEATING, TYPE_AIR_CONDITIONING]:
                entity = create_climate_entity(tado, zone["name"], zone["id"])
                if entity:
                    entities.append(entity)

    if entities:
        add_entities(entities, True)


def create_climate_entity(tado, name: str, zone_id: int):
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
    )
    return entity


class TadoClimate(ClimateDevice):
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
    ):
        """Initialize of Tado climate entity."""
        self._tado = tado

        self.zone_name = zone_name
        self.zone_id = zone_id
        self.zone_type = zone_type
        self._unique_id = f"{zone_type} {zone_id} {tado.device_id}"

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

        self._undo_dispatcher = None
        self._tado_zone_data = None
        self._async_update_zone_data()

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        if self._undo_dispatcher:
            self._undo_dispatcher()

    async def async_added_to_hass(self):
        """Register for sensor updates."""

        self._undo_dispatcher = async_dispatcher_connect(
            self.hass,
            SIGNAL_TADO_UPDATE_RECEIVED.format("zone", self.zone_id),
            self._async_update_callback,
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
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

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

    @callback
    def _async_update_zone_data(self):
        """Load tado data into zone."""
        self._tado_zone_data = self._tado.data["zone"][self.zone_id]
        self._current_tado_fan_speed = self._tado_zone_data.current_fan_speed
        self._current_tado_hvac_mode = self._tado_zone_data.current_hvac_mode
        self._current_tado_hvac_action = self._tado_zone_data.current_hvac_action

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

    def _control_hvac(self, hvac_mode=None, target_temp=None, fan_mode=None):
        """Send new target temperature to Tado."""

        if hvac_mode:
            self._current_tado_hvac_mode = hvac_mode

        if target_temp:
            self._target_temp = target_temp

        if fan_mode:
            self._current_tado_fan_speed = fan_mode

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
            "Switching to %s for zone %s (%d) with temperature %s °C",
            self._current_tado_hvac_mode,
            self.zone_name,
            self.zone_id,
            self._target_temp,
        )

        # Fallback to Smart Schedule at next Schedule switch if we have fallback enabled
        overlay_mode = (
            CONST_OVERLAY_TADO_MODE if self._tado.fallback else CONST_OVERLAY_MANUAL
        )

        temperature_to_send = self._target_temp
        if self._current_tado_hvac_mode in TADO_MODES_WITH_NO_TEMP_SETTING:
            # A temperature cannot be passed with these modes
            temperature_to_send = None

        self._tado.set_zone_overlay(
            zone_id=self.zone_id,
            overlay_mode=overlay_mode,  # What to do when the period ends
            temperature=temperature_to_send,
            duration=None,
            device_type=self.zone_type,
            mode=self._current_tado_hvac_mode,
            fan_speed=(
                self._current_tado_fan_speed
                if (self._support_flags & SUPPORT_FAN_MODE)
                else None
            ),  # api defaults to not sending fanSpeed if not specified
        )
