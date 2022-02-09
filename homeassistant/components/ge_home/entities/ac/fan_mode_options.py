import logging
from typing import Any, List, Optional

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
)
from gehomesdk import ErdAcFanSetting
from ..common import OptionsConverter

_LOGGER = logging.getLogger(__name__)

class AcFanModeOptionsConverter(OptionsConverter):
    def __init__(self, default_option: ErdAcFanSetting = ErdAcFanSetting.AUTO):
        self._default = default_option
       
    @property
    def options(self) -> List[str]:
        return [i.stringify() for i in [ErdAcFanSetting.AUTO, ErdAcFanSetting.LOW, ErdAcFanSetting.MED, ErdAcFanSetting.HIGH]]
 
    def from_option_string(self, value: str) -> Any:
        try:
            return ErdAcFanSetting[value.upper().replace(" ","_")]
        except:
            _LOGGER.warn(f"Could not set fan mode to {value}")
            return self._default

    def to_option_string(self, value: Any) -> Optional[str]:
        try:
            return {
                ErdAcFanSetting.AUTO: ErdAcFanSetting.AUTO,
                ErdAcFanSetting.LOW: ErdAcFanSetting.LOW,
                ErdAcFanSetting.LOW_AUTO: ErdAcFanSetting.AUTO,
                ErdAcFanSetting.MED: ErdAcFanSetting.MED,
                ErdAcFanSetting.MED_AUTO: ErdAcFanSetting.AUTO,
                ErdAcFanSetting.HIGH: ErdAcFanSetting.HIGH,
                ErdAcFanSetting.HIGH_AUTO: ErdAcFanSetting.HIGH
            }.get(value).stringify()
        except:
            pass
        return self._default.stringify()

class AcFanOnlyFanModeOptionsConverter(AcFanModeOptionsConverter):
    def __init__(self):
        super().__init__(ErdAcFanSetting.LOW)

    @property
    def options(self) -> List[str]:
        return [i.stringify() for i in [ErdAcFanSetting.LOW, ErdAcFanSetting.MED, ErdAcFanSetting.HIGH]]
