"""Parser for Window AC (008-399) device type."""
from typing import Dict

from .base import BaseDeviceParser, DeviceAttribute

class WindowAC008399Parser(BaseDeviceParser):
    """Parser for Window AC 008-399 device type."""
    
    @property
    def device_type(self) -> str:
        return "008"
        
    @property
    def feature_code(self) -> str:
        return "399"
        
    @property
    def attributes(self) -> Dict[str, DeviceAttribute]:
        return {
            "t_work_mode": DeviceAttribute(
                key="t_work_mode",
                name="设定模式",
                attr_type="Enum",
                step=1,
                value_range="0,1,2,3,5",
                value_map={
                    "0": "送风",
                    "1": "制热",
                    "2": "制冷",
                    "3": "除湿",
                    "5": "E-star"
                },
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
            "t_temp": DeviceAttribute(
                key="t_temp",
                name="设置温度",
                attr_type="Number",
                step=1,
                value_range="16~30,61~86",
                read_write="RW"
            ),
            "t_fan_speed": DeviceAttribute(
                key="t_fan_speed",
                name="设定风速",
                attr_type="Enum",
                step=1,
                value_range="5,7,9",
                value_map={
                    "5": "低风",
                    "7": "中风",
                    "9": "高风"
                },
                read_write="RW"
            ),
            "t_power_consumption": DeviceAttribute(
                key="t_power_consumption",
                name="电量累积消耗值",
                attr_type="Number",
                read_write="R"
            ),
            "t_fan_mute": DeviceAttribute(
                key="t_fan_mute",
                name="设定静音",
                attr_type="Enum",
                step=1,
                value_range="0,1",
                value_map={
                    "0": "停",
                    "1": "开"
                },
                read_write="RW"
            ),
            "t_super": DeviceAttribute(
                key="t_super",
                name="强力",
                attr_type="Enum",
                step=1,
                value_range="0,1",
                value_map={
                    "0": "取消",
                    "1": "开启"
                },
                read_write="RW"
            ),
            "t_temp_in": DeviceAttribute(
                key="t_temp_in",
                name="室内温度",
                attr_type="Number",
                read_write="R"
            )
        }
