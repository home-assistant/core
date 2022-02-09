import logging
from typing import List, Any, Optional

from gehomesdk import ErdCodeType, ErdHoodFanSpeedAvailability, ErdHoodFanSpeed, ErdCode
from ...devices import ApplianceApi
from ..common import GeErdSelect, OptionsConverter

_LOGGER = logging.getLogger(__name__)

class HoodFanSpeedOptionsConverter(OptionsConverter):
    def __init__(self, availability: ErdHoodFanSpeedAvailability):
        super().__init__()
        self.availability = availability
        self.excluded_speeds = []
        if not availability.off_available:
            self.excluded_speeds.append(ErdHoodFanSpeed.OFF)
        if not availability.low_available:
            self.excluded_speeds.append(ErdHoodFanSpeed.LOW)
        if not availability.med_available:
            self.excluded_speeds.append(ErdHoodFanSpeed.MEDIUM)
        if not availability.high_available:
            self.excluded_speeds.append(ErdHoodFanSpeed.HIGH)
        if not availability.boost_available:
            self.excluded_speeds.append(ErdHoodFanSpeed.BOOST)

    @property
    def options(self) -> List[str]:
        return [i.stringify() for i in ErdHoodFanSpeed if i not in self.excluded_speeds]
    def from_option_string(self, value: str) -> Any:
        try:
            return ErdHoodFanSpeed[value.upper()]
        except:
            _LOGGER.warn(f"Could not set hood fan speed to {value.upper()}")
            return ErdHoodFanSpeed.OFF
    def to_option_string(self, value: ErdHoodFanSpeed) -> Optional[str]:
        try:
            if value is not None:
                return value.stringify()
        except:
            pass
        return ErdHoodFanSpeed.OFF.stringify()

class GeHoodFanSpeedSelect(GeErdSelect):
    def __init__(self, api: ApplianceApi, erd_code: ErdCodeType):
        self._availability: ErdHoodFanSpeedAvailability = api.try_get_erd_value(ErdCode.HOOD_FAN_SPEED_AVAILABILITY)
        super().__init__(api, erd_code, HoodFanSpeedOptionsConverter(self._availability))
