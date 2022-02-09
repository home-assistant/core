import logging
from typing import Any, List, Optional

from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
)
from gehomesdk import ErdAcOperationMode
from ...devices import ApplianceApi
from ..common import GeClimate, OptionsConverter
from .fan_mode_options import AcFanModeOptionsConverter, AcFanOnlyFanModeOptionsConverter

_LOGGER = logging.getLogger(__name__)

class WacHvacModeOptionsConverter(OptionsConverter):
    @property
    def options(self) -> List[str]:
        return [HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY]
    def from_option_string(self, value: str) -> Any:
        try:
            return {
                HVAC_MODE_AUTO: ErdAcOperationMode.ENERGY_SAVER,
                HVAC_MODE_COOL: ErdAcOperationMode.COOL,
                HVAC_MODE_FAN_ONLY: ErdAcOperationMode.FAN_ONLY
            }.get(value)
        except:
            _LOGGER.warn(f"Could not set HVAC mode to {value.upper()}")
            return ErdAcOperationMode.COOL
    def to_option_string(self, value: Any) -> Optional[str]:
        try:
            return {
                ErdAcOperationMode.ENERGY_SAVER: HVAC_MODE_AUTO,
                ErdAcOperationMode.AUTO: HVAC_MODE_AUTO,
                ErdAcOperationMode.COOL: HVAC_MODE_COOL,
                ErdAcOperationMode.FAN_ONLY: HVAC_MODE_FAN_ONLY
            }.get(value)
        except:
            _LOGGER.warn(f"Could not determine operation mode mapping for {value}")
            return HVAC_MODE_COOL
  
class GeWacClimate(GeClimate):
    """Class for Window AC units"""
    def __init__(self, api: ApplianceApi):
        super().__init__(api, WacHvacModeOptionsConverter(), AcFanModeOptionsConverter(), AcFanOnlyFanModeOptionsConverter())
