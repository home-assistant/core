"""GE Home Sensor Entities - Advantium"""
import logging
from typing import Any, Dict, List, Mapping, Optional, Set
from random import randrange

from gehomesdk import (
    ErdCode,
    ErdUnitType,
    ErdAdvantiumCookStatus, 
    ErdAdvantiumCookSetting, 
    AdvantiumOperationMode, 
    AdvantiumCookSetting,
    ErdAdvantiumRemoteCookModeConfig,
    ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING     
)
from gehomesdk.erd.values.advantium.advantium_enums import CookAction, CookMode

from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from ...const import DOMAIN
from ...devices import ApplianceApi
from ..common import GeWaterHeater
from .const import *

_LOGGER = logging.getLogger(__name__)

class GeAdvantium(GeWaterHeater):
    """GE Appliance Advantium"""

    icon = "mdi:microwave"

    def __init__(self, api: ApplianceApi):
        super().__init__(api)

    @property
    def supported_features(self):
        if self.remote_enabled:
            return GE_ADVANTIUM_WITH_TEMPERATURE if self.can_set_temperature else GE_ADVANTIUM
        else:
            return SUPPORT_NONE

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.serial_number}"

    @property
    def name(self) -> Optional[str]:
        return f"{self.serial_number} Advantium"

    @property
    def unit_type(self) -> Optional[ErdUnitType]:
        try:
            return self.appliance.get_erd_value(ErdCode.UNIT_TYPE)
        except:
            return None

    @property
    def remote_enabled(self) -> bool:
        """Returns whether the oven is remote enabled"""
        value = self.appliance.get_erd_value(ErdCode.UPPER_OVEN_REMOTE_ENABLED)
        return value == True

    @property
    def current_temperature(self) -> Optional[int]:
        return self.appliance.get_erd_value(ErdCode.UPPER_OVEN_DISPLAY_TEMPERATURE)

    @property
    def current_operation(self) -> Optional[str]:
        try:
            return self.current_operation_mode.stringify()
        except:
            return None

    @property
    def operation_list(self) -> List[str]:
        invalid = []
        if not self._remote_config.broil_enable:
            invalid.append(CookMode.BROIL)
        if not self._remote_config.convection_bake_enable:
            invalid.append(CookMode.CONVECTION_BAKE)
        if not self._remote_config.proof_enable:
            invalid.append(CookMode.PROOF)
        if not self._remote_config.warm_enable:
            invalid.append(CookMode.WARM)

        return [
            k.stringify()
            for k, v in ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING.items() 
            if v.cook_mode not in invalid]

    @property
    def current_cook_setting(self) -> ErdAdvantiumCookSetting:
        """Get the current cook setting."""
        return self.appliance.get_erd_value(ErdCode.ADVANTIUM_COOK_SETTING)

    @property
    def current_cook_status(self) -> ErdAdvantiumCookStatus:
        """Get the current status."""
        return self.appliance.get_erd_value(ErdCode.ADVANTIUM_COOK_STATUS)

    @property
    def current_operation_mode(self) -> AdvantiumOperationMode:
        """Gets the current operation mode"""
        return self._current_operation_mode

    @property
    def current_operation_setting(self) -> Optional[AdvantiumCookSetting]:
        if self.current_operation_mode is None:
            return None
        try:
            return ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING[self.current_operation_mode]
        except:
            _LOGGER.debug(f"Unable to determine operation setting, mode = {self.current_operation_mode}")
            return None
            
    @property
    def can_set_temperature(self) -> bool:
        """Indicates whether we can set the temperature based on the current mode"""
        try:            
            return self.current_operation_setting.allow_temperature_set
        except:
            return False

    @property
    def target_temperature(self) -> Optional[int]:
        """Return the temperature we try to reach."""
        try:
            cook_mode = self.current_cook_setting
            if cook_mode.target_temperature and cook_mode.target_temperature > 0:
                return cook_mode.target_temperature
        except:
            pass
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

    @property
    def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
        data = {}

        cook_time_remaining = self.appliance.get_erd_value(ErdCode.ADVANTIUM_COOK_TIME_REMAINING)
        kitchen_timer = self.appliance.get_erd_value(ErdCode.ADVANTIUM_KITCHEN_TIME_REMAINING)
        data["unit_type"] = self._stringify(self.unit_type)
        if cook_time_remaining:
            data["cook_time_remaining"] = self._stringify(cook_time_remaining)
        if kitchen_timer:
            data["kitchen_timer"] = self._stringify(kitchen_timer)
        return data

    @property
    def _remote_config(self) -> ErdAdvantiumRemoteCookModeConfig:
        return self.appliance.get_erd_value(ErdCode.ADVANTIUM_REMOTE_COOK_MODE_CONFIG)  

    async def async_set_operation_mode(self, operation_mode: str):
        """Set the operation mode."""

        #try to get the mode/setting for the selection
        try:
            mode = AdvantiumOperationMode(operation_mode)
            setting = ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING[mode]
        except:
            _LOGGER.debug(f"Attempted to set mode to {operation_mode}, unknown.")
            return

        #determine the target temp for this mode
        target_temp = self._convert_target_temperature(setting.target_temperature_120v_f, setting.target_temperature_240v_f)

        #if we allow temperature to be set in this mode, and already have a temperature, use it
        if setting.allow_temperature_set and self.target_temperature:
            target_temp = self.target_temperature

        #by default we will start an operation, but handle other actions too
        action = CookAction.START
        if mode == AdvantiumOperationMode.OFF:
            action = CookAction.STOP
        elif self.current_cook_setting.cook_action == CookAction.PAUSE:
            action = CookAction.RESUME
        elif self.current_cook_setting.cook_action in [CookAction.START, CookAction.RESUME]:
            action = CookAction.UPDATED

        #construct the new mode based on the existing mode
        new_cook_mode = self.current_cook_setting
        new_cook_mode.d = randrange(255)
        new_cook_mode.target_temperature = target_temp
        if(setting.target_power_level != 0):
            new_cook_mode.power_level = setting.target_power_level
        new_cook_mode.cook_mode = setting.cook_mode
        new_cook_mode.cook_action = action

        await self.appliance.async_set_erd_value(ErdCode.ADVANTIUM_COOK_SETTING, new_cook_mode)

    async def async_set_temperature(self, **kwargs):
        """Set the cook temperature"""

        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return

        #get the current mode/operation
        mode = self.current_operation_mode
        setting = self.current_operation_setting

        #if we can't figure out the mode/setting, exit
        if mode is None or setting is None:
            return 

        #if we're off or can't set temperature, just exit
        if mode == AdvantiumOperationMode.OFF or not setting.allow_temperature_set:
            return

        #should only need to update
        action = CookAction.UPDATED

        #construct the new mode based on the existing mode
        new_cook_mode = self.current_cook_setting
        new_cook_mode.d = randrange(255)
        new_cook_mode.target_temperature = target_temp
        new_cook_mode.cook_action = action

        await self.appliance.async_set_erd_value(ErdCode.ADVANTIUM_COOK_SETTING, new_cook_mode)            

    async def _ensure_operation_mode(self):
        cook_setting = self.current_cook_setting
        cook_mode = cook_setting.cook_mode  

        #if we have a current mode
        if(self._current_operation_mode is not None):
            #and the cook mode is the same as what the appliance says, we'll just leave things alone
            #and assume that things are in sync
            if ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING[self._current_operation_mode].cook_mode == cook_mode:
                return
            else:
                self._current_operation_mode = None
        
        #synchronize the operation mode with the device state
        if cook_mode == CookMode.MICROWAVE:
            #microwave matches on cook mode and power level
            if cook_setting.power_level == 3:
                self._current_operation_mode = AdvantiumOperationMode.MICROWAVE_PL3
            elif cook_setting.power_level == 5:
                self._current_operation_mode = AdvantiumOperationMode.MICROWAVE_PL5
            elif cook_setting.power_level == 7:
                self._current_operation_mode = AdvantiumOperationMode.MICROWAVE_PL7
            else:
                self._current_operation_mode = AdvantiumOperationMode.MICROWAVE_PL10
        elif cook_mode == CookMode.WARM:
            for key, value in ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING.items():
                #warm matches on the mode, warm status, and target temp
                if (cook_mode == value.cook_mode and 
                    cook_setting.warm_status == value.warm_status and 
                    cook_setting.target_temperature == self._convert_target_temperature(
                        value.target_temperature_120v_f, value.target_temperature_240v_f)):
                    self._current_operation_mode = key
                    return

        #just pick the first match based on cook mode if we made it here
        if self._current_operation_mode is None:
            for key, value in ADVANTIUM_OPERATION_MODE_COOK_SETTING_MAPPING.items():
                if cook_mode == value.cook_mode:
                    self._current_operation_mode = key
                    return

    async def _convert_target_temperature(self, temp_120v: int, temp_240v: int):
        unit_type = self.unit_type
        target_temp_f = temp_240v if unit_type in [ErdUnitType.TYPE_240V_MONOGRAM, ErdUnitType.TYPE_240V_CAFE] else temp_120v
        if self.temperature_unit == TEMP_FAHRENHEIT:
            return float(target_temp_f)
        else:
            return (target_temp_f - 32.0) * (5/9)

    async def async_device_update(self, warning: bool) -> None:
        await super().async_device_update(warning=warning)
        await self._ensure_operation_mode()
