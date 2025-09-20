"""Parser for Split AC (009-199) device type."""
from typing import Dict

from .base import BaseDeviceParser, DeviceAttribute

class SplitAC009199Parser(BaseDeviceParser):
    """Parser for Split AC 009-199 device type."""
    
    @property
    def device_type(self) -> str:
        return "009"
        
    @property
    def feature_code(self) -> str:
        return "199"
        
    @property
    def attributes(self) -> Dict[str, DeviceAttribute]:
        return {
            "t_work_mode": DeviceAttribute(
                key="t_work_mode",
                name="设定模式",
                attr_type="Enum",
                step=1,
                value_range="0,1,2,3,4",
                value_map={
                    "0": "送风",
                    "1": "制热",
                    "2": "制冷",
                    "3": "除湿",
                    "4": "自动"
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
                value_range="16~32,61~90",
                read_write="RW"
            ),
            "t_fan_speed": DeviceAttribute(
                key="t_fan_speed",
                name="设定风速",
                attr_type="Enum",
                step=1,
                value_range="0,5,6,7,8,9",
                value_map={
                    "0": "自动",
                    "5": "超低",
                    "6": "低",
                    "7": "中",
                    "8": "高",
                    "9": "超高"
                },
                read_write="RW"
            ),
            "t_up_down": DeviceAttribute(
                key="t_up_down",
                name="上下风",
                attr_type="Enum",
                step=1,
                value_range="0,1",
                value_map={
                    "0": "取消",
                    "1": "开启"
                },
                read_write="RW"
            ),
            "t_left_right": DeviceAttribute(
                key="t_left_right",
                name="左右风",
                attr_type="Enum",
                step=1,
                value_range="0,1",
                value_map={
                    "0": "取消",
                    "1": "开启"
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
            ),
            "t_8heat": DeviceAttribute(
                key="t_8heat",
                name="8°制热",
                attr_type="Enum",
                step=1,
                value_range="0,1",
                value_map={
                    "0": "关闭",
                    "1": "开启"
                },
                read_write="RW"
            )
        }
