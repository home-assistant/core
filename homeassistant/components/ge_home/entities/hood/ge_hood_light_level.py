import logging
from typing import List, Any, Optional

from gehomesdk import ErdCodeType, ErdHoodLightLevelAvailability, ErdHoodLightLevel, ErdCode
from ...devices import ApplianceApi
from ..common import GeErdSelect, OptionsConverter

_LOGGER = logging.getLogger(__name__)

class HoodLightLevelOptionsConverter(OptionsConverter):
    def __init__(self, availability: ErdHoodLightLevelAvailability):
        super().__init__()
        self.availability = availability
        self.excluded_levels = []
        if not availability.off_available:
            self.excluded_levels.append(ErdHoodLightLevel.OFF)
        if not availability.dim_available:
            self.excluded_levels.append(ErdHoodLightLevel.DIM)
        if not availability.high_available:
            self.excluded_levels.append(ErdHoodLightLevel.HIGH)

    @property
    def options(self) -> List[str]:
        return [i.stringify() for i in ErdHoodLightLevel if i not in self.excluded_levels]
    def from_option_string(self, value: str) -> Any:
        try:
            return ErdHoodLightLevel[value.upper()]
        except:
            _LOGGER.warn(f"Could not set hood light level to {value.upper()}")
            return ErdHoodLightLevel.OFF
    def to_option_string(self, value: ErdHoodLightLevel) -> Optional[str]:
        try:
            if value is not None:
                return value.stringify()
        except:
            pass
        return ErdHoodLightLevel.OFF.stringify()

class GeHoodLightLevelSelect(GeErdSelect):
    def __init__(self, api: ApplianceApi, erd_code: ErdCodeType):
        self._availability: ErdHoodLightLevelAvailability = api.try_get_erd_value(ErdCode.HOOD_LIGHT_LEVEL_AVAILABILITY)
        super().__init__(api, erd_code, HoodLightLevelOptionsConverter(self._availability))
