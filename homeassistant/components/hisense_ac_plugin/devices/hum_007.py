"""Parser for Split AC (009-199) device type."""
from typing import Dict

from .base import BaseDeviceParser, DeviceAttribute

class Humidity007Parser(BaseDeviceParser):
    """Parser for Split AC 009-199 device type."""
    
    @property
    def device_type(self) -> str:
        return "007"
        
    @property
    def feature_code(self) -> str:
        return ""


    @property
    def attributes(self) -> Dict[str, DeviceAttribute]:
        if not hasattr(self, '_attributes'):
            self._attributes = {
                "t_work_mode": DeviceAttribute(
                    key="t_work_mode",
                    name="设定模式",
                    attr_type="Enum",
                    step=1,
                    value_range="1, 0, 15, 5, 6, 16, 3",
                    value_map={
                        "0": "持续",
                        "1": "正常",
                        "2": "自动",
                        "3": "干衣"
                    },
                    read_write="RW"
                ),
                "t_humidity": DeviceAttribute(
                    key="t_humidity",
                    name="设定湿度值",
                    attr_type="Number",
                    step=5,
                    value_range="30~80",
                    read_write="RW"
                ),
                "f_humidity": DeviceAttribute(
                    key="f_humidity",
                    name="实际湿度",
                    attr_type="Number",
                    step=1,
                    value_range="30~90",
                    read_write="R"
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
                "t_fan_speed": DeviceAttribute(
                    key="t_fan_speed",
                    name="设定风速",
                    attr_type="Enum",
                    step=1,
                    value_range="0,5,6,7,8,9",
                    value_map={
                        "2": "自动",
                        "3": "中风",
                        "1": "高风",
                        "0": "低风"
                    },
                    read_write="RW"
                ),
                "f_power_consumption": DeviceAttribute(
                    key="f_power_consumption",
                    name="电量累积消耗值",
                    attr_type="Number",
                    read_write="R"
                ),
            }
        return self._attributes

    def remove_attribute(self, key: str) -> None:
        """移除指定的属性"""
        if key in self._attributes:
            del self._attributes[key]