"""Parser for Split AC (009-199) device type."""
from typing import Dict

from .base import BaseDeviceParser, DeviceAttribute

class SplitWater035699Parser(BaseDeviceParser):
    """Parser for Split AC 009-199 device type."""
    
    @property
    def device_type(self) -> str:
        return "035"
        
    @property
    def feature_code(self) -> str:
        return "699"
        
    @property
    def attributes(self) -> Dict[str, DeviceAttribute]:
        return {
            "t_work_mode": DeviceAttribute(
                key="t_work_mode",
                name="设定模式",
                attr_type="Enum",
                step=1,
                value_range="1, 0, 15, 5, 6, 16, 3",
                value_map={
                    "0": "制热",
                    "1": "制冷",
                    "15": "自动",
                    "5": "热水+制冷",
                    "16": "热水+自动",
                    "3": "热水",
                    "6": "热水+制热"
                },
                read_write="RW"
            ),
            "t_temp": DeviceAttribute(
                key="t_temp",
                name="设置温度",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="RW"
            ),
            "t_power": DeviceAttribute(
                key="t_power",
                name="开关机",
                attr_type="Enum",
                step=1,
                value_range="0,1",
                value_map={
                    "0": "关",
                    "1": "开"
                },
                read_write="RW"
            ),
            "f_zone1water_temp1": DeviceAttribute(
                key="f_zone1water_temp1",
                name="1温区实际值",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="R"
            ),
            "f_zone2water_temp2": DeviceAttribute(
                key="f_zone2water_temp2",
                name="2温区实际值",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="R"
            ),
            "f_water_tank_temp": DeviceAttribute(
                key="f_water_tank_temp",
                name="生活热水实际值",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="R"
            ),
            "t_zone1water_settemp1": DeviceAttribute(
                key="t_zone1water_settemp1",
                name="1温区设置值",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="RW"
            ),
            "t_zone2water_settemp2": DeviceAttribute(
                key="t_zone2water_settemp2",
                name="2温区设置值",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="RW"
            ),
            "t_dhw_temp": DeviceAttribute(
                key="t_dhw_temp",
                name="生活热水设置值",
                attr_type="Number",
                step=1,
                value_range="16~32,61~90",
                read_write="RW"
            ),
            "f_power_consumption": DeviceAttribute(
                key="f_power_consumption",
                name="电量累积消耗值",
                attr_type="Number",
                read_write="R"
            ),
        }

    def remove_attribute(self, key: str) -> None:
        """移除指定的属性"""
        attributes = self.attributes
        if key in attributes:
            del attributes[key]
