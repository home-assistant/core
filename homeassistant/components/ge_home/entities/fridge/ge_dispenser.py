"""GE Home Sensor Entities - Dispenser"""

import logging
from typing import List, Optional, Dict, Any

from homeassistant.const import ATTR_TEMPERATURE, TEMP_FAHRENHEIT
from homeassistant.util.temperature import convert as convert_temperature

from gehomesdk import (
    ErdCode,
    ErdHotWaterStatus,
    ErdPresent,
    ErdPodStatus,
    ErdFullNotFull,
    HotWaterStatus
)

from ..common import GeWaterHeater
from .const import (
    HEATER_TYPE_DISPENSER, 
    OP_MODE_NORMAL,
    OP_MODE_SABBATH,
    GE_FRIDGE_SUPPORT
)

_LOGGER = logging.getLogger(__name__)

class GeDispenser(GeWaterHeater):
    """Entity for in-fridge dispensers"""
    
    # These values are from FridgeHotWaterFragment.smali in the android app (in imperial units)
    # However, the k-cup temperature max appears to be 190.  Since there doesn't seem to be any
    # Difference between normal heating and k-cup heating based on what I see in the app, 
    # we will just set the max temp to 190 instead of the 185
    _min_temp = 90
    _max_temp = 190 #185
    icon = "mdi:cup-water"
    heater_type = HEATER_TYPE_DISPENSER

    @property
    def hot_water_status(self) -> HotWaterStatus:
        """Access the main status value conveniently."""
        return self.appliance.get_erd_value(ErdCode.HOT_WATER_STATUS)

    @property
    def supports_k_cups(self) -> bool:
        """Return True if the device supports k-cup brewing."""
        status = self.hot_water_status
        return status.pod_status != ErdPodStatus.NA and status.brew_module != ErdPresent.NA

    @property
    def operation_list(self) -> List[str]:
        """Supported Operations List"""
        ops_list = [OP_MODE_NORMAL, OP_MODE_SABBATH]
        return ops_list

    async def async_set_temperature(self, **kwargs):
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        if target_temp is None:
            return
        if not self.min_temp <= target_temp <= self.max_temp:
            raise ValueError("Tried to set temperature out of device range")
    
        await self.appliance.async_set_erd_value(ErdCode.HOT_WATER_SET_TEMP, target_temp)

    async def async_set_sabbath_mode(self, sabbath_on: bool = True):
        """Set sabbath mode if it's changed"""
        if self.appliance.get_erd_value(ErdCode.SABBATH_MODE) == sabbath_on:
            return
        await self.appliance.async_set_erd_value(ErdCode.SABBATH_MODE, sabbath_on)

    async def async_set_operation_mode(self, operation_mode):
        """Set the operation mode."""
        if operation_mode not in self.operation_list:
            raise ValueError("Invalid operation mode")
        if operation_mode == self.current_operation:
            return
        sabbath_mode = operation_mode == OP_MODE_SABBATH
        await self.async_set_sabbath_mode(sabbath_mode)

    @property
    def supported_features(self):
        return GE_FRIDGE_SUPPORT

    @property
    def current_operation(self) -> str:
        """Get the current operation mode."""
        if self.appliance.get_erd_value(ErdCode.SABBATH_MODE):
            return OP_MODE_SABBATH
        return OP_MODE_NORMAL

    @property
    def current_temperature(self) -> Optional[int]:
        """Return the current temperature."""
        return self.hot_water_status.current_temp

    @property
    def target_temperature(self) -> Optional[int]:
        """Return the target temperature."""
        return self.appliance.get_erd_value(ErdCode.HOT_WATER_SET_TEMP)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(self._min_temp, TEMP_FAHRENHEIT, self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(self._max_temp, TEMP_FAHRENHEIT, self.temperature_unit)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        data = {}
        
        data["target_temperature"] = self.target_temperature
        if self.hot_water_status.status in [ErdHotWaterStatus.FAULT_LOCKED_OUT, ErdHotWaterStatus.FAULT_NEED_CLEARED]:
            data["fault_status"] = self._stringify(self.hot_water_status.status)
        if self.supports_k_cups:
            data["pod_status"] = self._stringify(self.hot_water_status.pod_status)
        if self.hot_water_status.time_until_ready:
            data["time_until_ready"] = self._stringify(self.hot_water_status.time_until_ready)
        if self.hot_water_status.tank_full != ErdFullNotFull.NA:
            data["tank_status"] = self._stringify(self.hot_water_status.tank_full)
        
        return data
