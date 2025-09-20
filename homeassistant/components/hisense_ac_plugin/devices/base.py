"""Base device parser class."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
import logging

_LOGGER = logging.getLogger(__name__)

@dataclass
class DeviceAttribute:
    """Device attribute definition."""
    key: str
    name: str
    attr_type: str
    step: int = 1
    value_range: Optional[str] = None#数值区间
    value_map: Optional[Dict[str, str]] = None#数值集合
    read_write: str = "RW"

class BaseDeviceParser(ABC):
    """Base class for device parsers."""
    
    @property
    @abstractmethod
    def device_type(self) -> str:
        """Return device type code."""
        pass
    
    @property
    @abstractmethod
    def feature_code(self) -> str:
        """Return feature code."""
        pass

    @property
    @abstractmethod
    def attributes(self) -> Dict[str, DeviceAttribute]:
        """Return device attributes."""
        pass
    def remove_attribute(self, key: str) -> None:
        """移除指定的属性"""
        attributes = self.attributes
        if key in attributes:
            del attributes[key]

    def parse_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Parse device status."""
        _LOGGER.debug(
            "Parsing status for device type %s-%s with attributes: %s",
            self.device_type,
            self.feature_code,
            {k: attr.name for k, attr in self.attributes.items()}
        )
        _LOGGER.debug("Raw status: %s", status)
        
        parsed_status = {}
        for key, attr in self.attributes.items():
            if key in status:
                value = status[key]
                try:
                    if attr.value_map and value in attr.value_map:
                        parsed_value = attr.value_map[value]
                        # _LOGGER.debug(
                        #     "Mapped attribute %s (%s) from %s to %s",
                        #     key, attr.name, value, parsed_value
                        # )
                    elif attr.attr_type == "Number":
                        parsed_value = float(value)
                        # _LOGGER.debug(
                        #     "Converted attribute %s (%s) to number: %s",
                        #     key, attr.name, parsed_value
                        # )
                    else:
                        parsed_value = value
                        # _LOGGER.debug(
                        #     "Using raw value for attribute %s (%s): %s",
                        #     key, attr.name, parsed_value
                        # )
                    parsed_status[key] = parsed_value
                except (ValueError, TypeError) as err:
                    _LOGGER.warning(
                        "Failed to parse attribute %s (%s) with value %s: %s",
                        key, attr.name, value, err
                    )
                    continue
        
        _LOGGER.debug("Parsed status: %s", parsed_status)
        return parsed_status
    
    def validate_value(self, key: str, value: Any) -> bool:
        """Validate value for a given attribute."""
        if key not in self.attributes:
            _LOGGER.warning("Attribute %s not found in device type %s-%s", 
                          key, self.device_type, self.feature_code)
            return False
            
        attr = self.attributes[key]
        if attr.read_write == "R":
            _LOGGER.warning("Attribute %s (%s) is read-only", key, attr.name)
            return False
            
        if attr.value_range:
            try:
                min_val, max_val = map(float, attr.value_range.split(","))
                value = float(value)
                valid = min_val <= value <= max_val
                if not valid:
                    _LOGGER.warning(
                        "Value %s for attribute %s (%s) is outside valid range %s-%s",
                        value, key, attr.name, min_val, max_val
                    )
                return valid
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Failed to validate range for attribute %s (%s): %s",
                    key, attr.name, err
                )
                return False
                
        if attr.value_map:
            valid = str(value) in attr.value_map.keys()
            if not valid:
                _LOGGER.warning(
                    "Value %s for attribute %s (%s) is not in valid map %s",
                    value, key, attr.name, list(attr.value_map.keys())
                )
            return valid
            
        return True
