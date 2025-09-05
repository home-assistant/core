# base_bean.py
from typing import Dict, List

from .base import BaseDeviceParser, DeviceAttribute
from .base_bean import BaseBeanParser

class Split006299Parser(BaseDeviceParser):

    @property
    def device_type(self) -> str:
        return "006"

    @property
    def feature_code(self) -> str:
        return "299"

    def remove_attribute(self, key: str) -> None:
        """移除指定的属性"""
        if key in self._attributes:
            del self._attributes[key]


    @property
    def attributes(self) -> Dict[str, DeviceAttribute]:
        if not hasattr(self, '_attributes'):
            self._attributes = {
                "t_work_mode": DeviceAttribute(
                    key="t_work_mode",
                    name="设定模式",
                    attr_type="Enum",
                    step=1,
                    value_range="0,1,2,3,4,5",
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
                        "5": "低",
                        "7": "中",
                        "9": "高"
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
                "t_temp_type": DeviceAttribute(
                    key="t_temp_type",
                    name="温度单位切换",
                    attr_type="Enum",
                    step=1,
                    value_range="0,1",
                    value_map={
                        "0": "摄氏",
                        "1": "华氏"
                    },
                    read_write="RW"
                ),
                "f_power_consumption": DeviceAttribute(
                    key="f_power_consumption",
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
                "f_temp_in": DeviceAttribute(
                    key="f_temp_in",
                    name="室内温度",
                    attr_type="Number",
                    read_write="R"
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
                )
            }
        return self._attributes

    @attributes.setter
    def attributes(self, value: Dict[str, DeviceAttribute]):
        self._attributes = value
