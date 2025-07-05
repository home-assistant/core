"""HomeKit Heater-Cooler accessory (single tile: temp / speed / swing).

Any Home Assistant climate entity that advertises fan or swing support is
exported as a single HeaterCooler service instead of Thermostat+Fan.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from pyhap.const import CATEGORY_THERMOSTAT

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as DOMAIN_CLIMATE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State, callback
from homeassistant.util.enum import try_parse_enum
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_ACTIVE,
    CHAR_COOLING_THRESHOLD_TEMPERATURE,
    CHAR_CURRENT_HEATER_COOLER_STATE,
    CHAR_CURRENT_TEMPERATURE,
    CHAR_HEATING_THRESHOLD_TEMPERATURE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_HEATER_COOLER_STATE,
    CHAR_TARGET_TEMPERATURE,
    PROP_MIN_STEP,
    SERV_HEATER_COOLER,
)
from .util import temperature_to_homekit, temperature_to_states

_LOGGER = logging.getLogger(__name__)

# ───────────── maps & constants ───────────────────────────────────────
HC_INACTIVE, HC_IDLE, HC_HEAT, HC_COOL = range(4)
HC_TARGET_OFF, HC_TARGET_HEAT, HC_TARGET_COOL, HC_TARGET_AUTO = range(4)

HC_HASS_TO_HOMEKIT_TARGET: Final = {
    HVACMode.OFF: HC_TARGET_OFF,
    HVACMode.HEAT: HC_TARGET_HEAT,
    HVACMode.COOL: HC_TARGET_COOL,
    HVACMode.HEAT_COOL: HC_TARGET_AUTO,
    HVACMode.AUTO: HC_TARGET_AUTO,
}
HC_HOMEKIT_TO_HASS_TARGET = {v: k for k, v in HC_HASS_TO_HOMEKIT_TARGET.items()}

HC_HASS_TO_HOMEKIT_ACTION: Final = {
    HVACAction.OFF: HC_INACTIVE,
    HVACAction.IDLE: HC_IDLE,
    HVACAction.HEATING: HC_HEAT,
    HVACAction.PREHEATING: HC_HEAT,
    HVACAction.COOLING: HC_COOL,
    HVACAction.DRYING: HC_COOL,
    HVACAction.FAN: HC_COOL,
    HVACAction.DEFROSTING: HC_HEAT,
}

ORDERED_FAN_SPEEDS = [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH]
SWING_ON_SET = {"on", "both", "horizontal", "vertical"}


# ───────────── helper functions ───────────────────────────────────────
def _hk_target_mode(state: State) -> int | None:
    """Map HA hvac_mode → HomeKit target heater-cooler state."""
    if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    if not (mode := try_parse_enum(HVACMode, state.state)):
        return None
    return HC_HASS_TO_HOMEKIT_TARGET.get(mode)


def _temp(state: State, key: str, unit: str) -> float | None:
    """Return a temperature attribute converted to HomeKit unit."""
    if (val := state.attributes.get(key)) is None:
        return None
    return temperature_to_homekit(val, unit)


# ───────────── accessory class ────────────────────────────────────────
@TYPES.register("HeaterCooler")
class HeaterCooler(HomeAccessory):
    """Expose a HA climate entity as a native HeaterCooler service."""

    # ──────────────────────────────────────────────────────────────────
    # Init
    # ──────────────────────────────────────────────────────────────────
    #
    def __init__(self, *args: Any) -> None:
        """Build the Heater-Cooler accessory and register HomeKit callbacks."""
        super().__init__(*args, category=CATEGORY_THERMOSTAT)
        self._unit = self.hass.config.units.temperature_unit

        state = self.hass.states.get(self.entity_id)
        assert state
        attrs = state.attributes
        feats = attrs.get(ATTR_SUPPORTED_FEATURES, 0)

        raw_step = attrs.get("temperature_step", 1)
        try:
            self._step: float = float(raw_step)
        except (TypeError, ValueError):
            self._step = 1.0

        # build characteristic list
        chars: list[str] = [
            CHAR_ACTIVE,
            CHAR_CURRENT_HEATER_COOLER_STATE,
            CHAR_TARGET_HEATER_COOLER_STATE,
            CHAR_CURRENT_TEMPERATURE,
            CHAR_TARGET_TEMPERATURE,
            CHAR_COOLING_THRESHOLD_TEMPERATURE,
            CHAR_HEATING_THRESHOLD_TEMPERATURE,
        ]
        if feats & ClimateEntityFeature.FAN_MODE:
            chars.append(CHAR_ROTATION_SPEED)
        if feats & ClimateEntityFeature.SWING_MODE:
            chars.append(CHAR_SWING_MODE)

        serv = self.add_preload_service(SERV_HEATER_COOLER, chars)
        self.set_primary_service(serv)

        # basic chars
        self.char_active = serv.configure_char(CHAR_ACTIVE, value=0)
        self.char_current_state = serv.configure_char(
            CHAR_CURRENT_HEATER_COOLER_STATE, value=HC_INACTIVE
        )
        self.char_target_state = serv.configure_char(
            CHAR_TARGET_HEATER_COOLER_STATE,
            value=HC_TARGET_OFF,
            setter_callback=self._set_target_state,
        )
        self.char_current_temp = serv.configure_char(
            CHAR_CURRENT_TEMPERATURE, value=21.0
        )

        # set-point chars (all share same props & setter)
        char_kwargs = {
            "properties": {PROP_MIN_STEP: self._step},
            "setter_callback": self._set_setpoint,
        }
        self.char_target_temp = serv.configure_char(
            CHAR_TARGET_TEMPERATURE, value=24.0, **char_kwargs
        )
        self.char_cool = serv.configure_char(
            CHAR_COOLING_THRESHOLD_TEMPERATURE, value=24.0, **char_kwargs
        )
        self.char_heat = serv.configure_char(
            CHAR_HEATING_THRESHOLD_TEMPERATURE, value=24.0, **char_kwargs
        )

        # fan / swing
        self.ordered_fan_speeds: list[str] = []
        if feats & ClimateEntityFeature.FAN_MODE and (
            modes := attrs.get(ATTR_FAN_MODES)
        ):
            fm = {m.lower(): m for m in modes}
            self.ordered_fan_speeds = [s for s in ORDERED_FAN_SPEEDS if s in fm]
            self.char_speed = serv.configure_char(
                CHAR_ROTATION_SPEED,
                value=100,
                properties={PROP_MIN_STEP: 100 / len(self.ordered_fan_speeds)},
                setter_callback=self._set_fan_speed,
            )
            self.fan_modes = fm

        if feats & ClimateEntityFeature.SWING_MODE and (
            sw := attrs.get(ATTR_SWING_MODES)
        ):
            self.swing_on_mode = next(
                (m for m in sw if m.lower() in SWING_ON_SET), sw[0]
            )
            self.char_swing = serv.configure_char(
                CHAR_SWING_MODE, value=0, setter_callback=self._set_swing_mode
            )

        # initialise
        self.async_update_state(state)
        serv.setter_callback = self._set_chars

    # ───────── HomeKit → HA setters ───────────────────────────────────
    def _set_target_state(self, value: int) -> None:
        """Handle writes to TargetHeaterCoolerState from HomeKit."""
        if value not in HC_HOMEKIT_TO_HASS_TARGET:
            return
        self.async_call_service(
            DOMAIN_CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_HVAC_MODE: HC_HOMEKIT_TO_HASS_TARGET[value],
            },
        )

    def _set_setpoint(self, value: float | None) -> None:
        """Send hi/lo OR single temp depending on entity capability."""
        if value is None:  # HomeKit sometimes sends a duplicate `None`
            return
        degrees = temperature_to_states(value, self._unit)
        state = self.hass.states.get(self.entity_id)
        assert state
        feats = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        data = (
            {ATTR_TARGET_TEMP_HIGH: degrees, ATTR_TARGET_TEMP_LOW: degrees}
            if feats & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            else {ATTR_TEMPERATURE: degrees}
        )
        data[ATTR_ENTITY_ID] = self.entity_id
        self.async_call_service(DOMAIN_CLIMATE, SERVICE_SET_TEMPERATURE, data)

    def _set_fan_speed(self, pct: int) -> None:
        mode = percentage_to_ordered_list_item(self.ordered_fan_speeds, pct - 1)
        self.async_call_service(
            DOMAIN_CLIMATE,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: self.entity_id, ATTR_FAN_MODE: mode},
        )

    def _set_swing_mode(self, on: int) -> None:
        mode = self.swing_on_mode if on else "off"
        self.async_call_service(
            DOMAIN_CLIMATE,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: self.entity_id, ATTR_SWING_MODE: mode},
        )

    def _set_chars(self, vals: dict[str, Any]) -> None:
        """Handle a characteristic *batch write* coming from HomeKit."""
        # --- target mode ----------------------------------------------------
        if CHAR_TARGET_HEATER_COOLER_STATE in vals:
            self._set_target_state(vals[CHAR_TARGET_HEATER_COOLER_STATE])

        # --- set-point(s) ----------------------------------------------------
        if any(
            k in vals
            for k in (
                CHAR_TARGET_TEMPERATURE,
                CHAR_COOLING_THRESHOLD_TEMPERATURE,
                CHAR_HEATING_THRESHOLD_TEMPERATURE,
            )
        ):
            # HomeKit numbers arrive as strings → cast to float for type-safety
            raw_val = (
                vals.get(CHAR_TARGET_TEMPERATURE)
                or vals.get(CHAR_COOLING_THRESHOLD_TEMPERATURE)
                or vals.get(CHAR_HEATING_THRESHOLD_TEMPERATURE)
            )
            new_val: float | None = None if raw_val is None else float(raw_val)
            self._set_setpoint(new_val)

    # ───────── HA → HomeKit updater ──────────────────────────────────
    @callback
    def async_update_state(self, new_state: State) -> None:
        """Mirror each Home Assistant state update to HomeKit."""
        attrs = new_state.attributes
        feats = attrs.get(ATTR_SUPPORTED_FEATURES, 0)

        if (tgt := _hk_target_mode(new_state)) is not None:
            self.char_target_state.set_value(tgt)

        action = attrs.get(ATTR_HVAC_ACTION) or self._derive_action(new_state)
        self.char_current_state.set_value(
            HC_HASS_TO_HOMEKIT_ACTION.get(action, HC_INACTIVE)
        )

        self.char_active.set_value(int(new_state.state != HVACMode.OFF))

        if (cur := _temp(new_state, ATTR_CURRENT_TEMPERATURE, self._unit)) is not None:
            self.char_current_temp.set_value(cur)

        # reflect the single set-point in all three chars
        sp = (
            _temp(new_state, ATTR_TARGET_TEMP_HIGH, self._unit)
            or _temp(new_state, ATTR_TARGET_TEMP_LOW, self._unit)
            or _temp(new_state, ATTR_TEMPERATURE, self._unit)
        )
        if sp is not None:
            self.char_target_temp.set_value(sp)
            self.char_cool.set_value(sp)
            self.char_heat.set_value(sp)

        if feats & ClimateEntityFeature.FAN_MODE and self.ordered_fan_speeds:
            fm = attrs.get(ATTR_FAN_MODE)
            if fm and (fm_l := fm.lower()) in self.ordered_fan_speeds:
                self.char_speed.set_value(
                    ordered_list_item_to_percentage(self.ordered_fan_speeds, fm_l)
                )

        if feats & ClimateEntityFeature.SWING_MODE and hasattr(self, "char_swing"):
            sw = attrs.get(ATTR_SWING_MODE)
            self.char_swing.set_value(1 if sw and sw.lower() in SWING_ON_SET else 0)

    # ───────── derive hvac_action if missing ──────────────────────────
    def _derive_action(self, state: State) -> HVACAction:
        """Infer heating / cooling when integration omits hvac_action."""
        mode = try_parse_enum(HVACMode, state.state)
        tgt = (
            state.attributes.get(ATTR_TEMPERATURE)
            or state.attributes.get(ATTR_TARGET_TEMP_HIGH)
            or state.attributes.get(ATTR_TARGET_TEMP_LOW)
        )
        cur = state.attributes.get(ATTR_CURRENT_TEMPERATURE)
        if cur is None or tgt is None or mode is None:
            return HVACAction.IDLE

        delta = 0.25  # °C hysteresis

        if mode == HVACMode.COOL:
            return HVACAction.COOLING if cur > tgt + delta else HVACAction.IDLE
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING if cur < tgt - delta else HVACAction.IDLE
        if mode in (HVACMode.HEAT_COOL, HVACMode.AUTO):
            if cur > tgt + delta:
                return HVACAction.COOLING
            if cur < tgt - delta:
                return HVACAction.HEATING
        return HVACAction.IDLE
