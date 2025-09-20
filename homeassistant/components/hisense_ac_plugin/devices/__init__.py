"""Device parsers package."""
from typing import Dict, Type
import logging

from .atw_035_699 import SplitWater035699Parser
from .base import BaseDeviceParser
from .base_bean import BaseBeanParser
from .hum_007 import Humidity007Parser
from .split_ac_009_199 import SplitAC009199Parser
from .window_ac_008_399 import WindowAC008399Parser
from .bean_006_299 import Split006299Parser

_LOGGER = logging.getLogger(__name__)

# Registry of device parsers
DEVICE_PARSERS: Dict[tuple[str, str], Type[BaseDeviceParser]] = {
    ("035", "699"): SplitWater035699Parser,
    ("006", "299"): Split006299Parser,
    ("007", ""): Humidity007Parser,
}


def get_device_parser(device_type: str , feature_code: str) -> Type[BaseDeviceParser]:
    """Get device parser for the given device type."""
    _LOGGER.debug("Getting device parser for type %s", device_type)
    if DEVICE_PARSERS.get((device_type, feature_code)):
        _LOGGER.debug("三联供设备 %s", device_type)
        return DEVICE_PARSERS[(device_type, feature_code)]
    if device_type == "007":
        _LOGGER.debug("除湿机设备 %s", device_type)
        return Humidity007Parser
    # 预设的设备类型集合
    supported_device_types = ["009", "008", "006", "016"]
    if device_type in supported_device_types:
        parser_class = BaseBeanParser
        _LOGGER.debug("Using default parser for device type %s", device_type)
        # try:
        #     static_data = await self.async_get_property_list(device_type, feature_code)
        #     _LOGGER.debug("Static data for device %s: %s: %s", device_type, feature_code, static_data)
        # except Exception as query_err:
        #     _LOGGER.error("Error querying static data for device %s: %s", feature_code, query_err)
        return parser_class
    else:
        _LOGGER.warning("Unsupported device type: %s", device_type)
        raise ValueError(f"Unsupported device type: {device_type}")

