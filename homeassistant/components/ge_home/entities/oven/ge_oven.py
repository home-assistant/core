"""GE Home Sensor Entities - Oven"""
import logging
from typing import Any, Dict, List, Optional, Set

from gehomesdk import (
    ErdCode,
    ErdMeasurementUnits,
    ErdOvenCookMode,
    OVEN_COOK_MODE_MAP,
    OvenCookSetting
)

from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common import GeWaterHeater
from .const import *

_LOGGER = logging.getLogger(__name__)

class GeOven(GeWaterHeater):
    """GE Appliance Oven"""

    icon = "mdi:stove"

    def __init__(self, api: ApplianceApi, oven_select: str = UPPER_OVEN, two_cavity: bool = False, temperature_erd_code: str = "RAW_TEMPERATURE"):
        if oven_select not in (UPPER_OVEN, LOWER_OVEN):
            raise ValueError(f"Invalid `oven_select` value ({oven_select})")

        self._oven_select = oven_select
        self._two_cavity = two_cavity
        self._temperature_erd_code = temperature_erd_code
        super().__init__(api)

    @property
    def supported_features(self):
        if self.remote_enabled:
            return GE_OVEN_SUPPORT
        else:
            return SUPPORT_NONE

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.serial_number}_{self.oven_select.lower()}"

    @property
    def name(self) -> Optional[str]:
        if self._two_cavity:
            oven_title = self.oven_select.replace("_", " ").title()
        else:
            oven_title = "Oven"

        return f"{self.serial_number} {oven_title}"

    @property
    def temperature_unit(self):
        measurement_system = self.appliance.get_erd_value(ErdCode.TEMPERATURE_UNIT)
        if measurement_system == ErdMeasurementUnits.METRIC:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def oven_select(self) -> str:
        return self._oven_select

    def get_erd_code(self, suffix: str) -> ErdCode:
        """Return the appropriate ERD code for this oven_select"""
        return ErdCode[f"{self.oven_select}_{suffix}"]

    @property
    def remote_enabled(self) -> bool:
        """Returns whether the oven is remote enabled"""
        value = self.get_erd_value("REMOTE_ENABLED")
        return value == True

    @property
    def current_temperature(self) -> Optional[int]:
        #DISPLAY_TEMPERATURE appears to be out of line with what's
        #actually going on in the oven, RAW_TEMPERATURE seems to be
        #accurate. However, it appears some devices don't have
        #the raw temperature.  So, we'll allow an override to handle
        #that situation (see constructor)
        #current_temp = self.get_erd_value("DISPLAY_TEMPERATURE")
        #if current_temp:
        #    return current_temp
        return self.get_erd_value(self._temperature_erd_code)

    @property
    def current_operation(self) -> Optional[str]:
        cook_setting = self.current_cook_setting
        cook_mode = cook_setting.cook_mode
        # TODO: simplify this lookup nonsense somehow
        current_state = OVEN_COOK_MODE_MAP.inverse[cook_mode]
        try:
            return COOK_MODE_OP_MAP[current_state]
        except KeyError:
            _LOGGER.debug(f"Unable to map {current_state} to an operation mode")
            return OP_MODE_COOK_UNK

    @property
    def operation_list(self) -> List[str]:
        #lookup all the available cook modes
        erd_code = self.get_erd_code("AVAILABLE_COOK_MODES")
        cook_modes: Set[ErdOvenCookMode] = self.appliance.get_erd_value(erd_code)
        _LOGGER.debug(f"Available Cook Modes: {cook_modes}")

        #get the extended cook modes and add them to the list
        ext_erd_code = self.get_erd_code("EXTENDED_COOK_MODES")
        ext_cook_modes: Set[ErdOvenCookMode] = self.api.try_get_erd_value(ext_erd_code)
        _LOGGER.debug(f"Extended Cook Modes: {ext_cook_modes}")
        if ext_cook_modes:
            cook_modes = cook_modes.union(ext_cook_modes)

        #make sure that we limit them to the list of known codes
        cook_modes = cook_modes.intersection(COOK_MODE_OP_MAP.keys())
        
        _LOGGER.debug(f"Final Cook Modes: {cook_modes}")
        op_modes = [o for o in (COOK_MODE_OP_MAP[c] for c in cook_modes) if o]
        op_modes = [OP_MODE_OFF] + op_modes
        return op_modes

    @property
    def current_cook_setting(self) -> OvenCookSetting:
        """Get the current cook mode."""
        erd_code = self.get_erd_code("COOK_MODE")
        return self.appliance.get_erd_value(erd_code)

    @property
    def target_temperature(self) -> Optional[int]:
        """Return the temperature we try to reach."""
        cook_mode = self.current_cook_setting
        if cook_mode.temperature:
            return cook_mode.temperature
        return None

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature."""
        min_temp, _ = self.appliance.get_erd_value(ErdCode.OVEN_MODE_MIN_MAX_TEMP)
        return min_temp

    @property
    def max_temp(self) -> int:
        """Return the maximum temperature."""
        _, max_temp = self.appliance.get_erd_value(ErdCode.OVEN_MODE_MIN_MAX_TEMP)
        return max_temp

    async def async_set_operation_mode(self, operation_mode: str):
        """Set the operation mode."""

        erd_cook_mode = COOK_MODE_OP_MAP.inverse[operation_mode]
        # Pick a temperature to set.  If there's not one already set, default to
        # good old 350F.
        if operation_mode == OP_MODE_OFF:
            target_temp = 0
        elif self.target_temperature:
            target_temp = self.target_temperature
        elif self.temperature_unit == TEMP_FAHRENHEIT:
            target_temp = 350
        else:
            target_temp = 177

        new_cook_mode = OvenCookSetting(OVEN_COOK_MODE_MAP[erd_cook_mode], target_temp)
        erd_code = self.get_erd_code("COOK_MODE")
        await self.appliance.async_set_erd_value(erd_code, new_cook_mode)

    async def async_set_temperature(self, **kwargs):
        """Set the cook temperature"""

        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        current_op = self.current_operation
        if current_op != OP_MODE_OFF:
            erd_cook_mode = COOK_MODE_OP_MAP.inverse[current_op]
        else:
            erd_cook_mode = ErdOvenCookMode.BAKE_NOOPTION

        new_cook_mode = OvenCookSetting(OVEN_COOK_MODE_MAP[erd_cook_mode], target_temp)
        erd_code = self.get_erd_code("COOK_MODE")
        await self.appliance.async_set_erd_value(erd_code, new_cook_mode)

    def get_erd_value(self, suffix: str) -> Any:
        erd_code = self.get_erd_code(suffix)
        return self.appliance.get_erd_value(erd_code)

    @property
    def display_state(self) -> Optional[str]:
        erd_code = self.get_erd_code("CURRENT_STATE")
        erd_value = self.appliance.get_erd_value(erd_code)
        return self._stringify(erd_value, temp_units=self.temperature_unit)

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        probe_present = False
        if self.api.has_erd_code(self.get_erd_code("PROBE_PRESENT")):
            probe_present: bool = self.get_erd_value("PROBE_PRESENT")
        data = {
            "display_state": self.display_state,
            "probe_present": probe_present,
            "display_temperature": self.get_erd_value("DISPLAY_TEMPERATURE")
        }
        if self.api.has_erd_code(self.get_erd_code("RAW_TEMPERATURE")):
            data["raw_temperature"] = self.get_erd_value("RAW_TEMPERATURE")
        if probe_present:
            data["probe_temperature"] = self.get_erd_value("PROBE_DISPLAY_TEMP")

        elapsed_time = None
        cook_time_remaining = None
        kitchen_timer = None
        delay_time = None
        if self.api.has_erd_code(self.get_erd_code("ELAPSED_COOK_TIME")):
            elapsed_time = self.get_erd_value("ELAPSED_COOK_TIME")
        if self.api.has_erd_code(self.get_erd_code("COOK_TIME_REMAINING")):
            cook_time_remaining = self.get_erd_value("COOK_TIME_REMAINING")
        if self.api.has_erd_code(self.get_erd_code("KITCHEN_TIMER")):
            kitchen_timer = self.get_erd_value("KITCHEN_TIMER")
        if self.api.has_erd_code(self.get_erd_code("DELAY_TIME_REMAINING")):
            delay_time = self.get_erd_value("DELAY_TIME_REMAINING")
        if elapsed_time:
            data["cook_time_elapsed"] = self._stringify(elapsed_time)
        if cook_time_remaining:
            data["cook_time_remaining"] = self._stringify(cook_time_remaining)
        if kitchen_timer:
            data["cook_time_remaining"] = self._stringify(kitchen_timer)
        if delay_time:
            data["delay_time_remaining"] = self._stringify(delay_time)
        return data
