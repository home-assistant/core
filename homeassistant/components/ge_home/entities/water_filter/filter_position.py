import logging
from typing import List, Any, Optional

from gehomesdk import ErdCodeType, ErdWaterFilterPosition, ErdCode, ErdWaterFilterMode
from ...devices import ApplianceApi
from ..common import GeErdSelect, OptionsConverter

_LOGGER = logging.getLogger(__name__)

class FilterPositionOptionsConverter(OptionsConverter):
    @property
    def options(self) -> List[str]:
        return [i.name.title() for i in ErdWaterFilterPosition if i != ErdWaterFilterPosition.UNKNOWN]
    def from_option_string(self, value: str) -> Any:
        try:
            return ErdWaterFilterPosition[value.upper()]
        except:
            _LOGGER.warn(f"Could not set filter position to {value.upper()}")
            return ErdWaterFilterPosition.UNKNOWN
    def to_option_string(self, value: Any) -> Optional[str]:
        try:
            if value is not None:
                return value.name.title()
        except:
            pass
        return ErdWaterFilterPosition.UNKNOWN.name.title()

class GeErdFilterPositionSelect(GeErdSelect):
    def __init__(self, api: ApplianceApi, erd_code: ErdCodeType):
        super().__init__(api, erd_code, FilterPositionOptionsConverter(), icon_override="mdi:valve")

    @property
    def current_option(self):
        """Return the current selected option"""
        
        #if we're transitioning or don't know what the mode is, don't allow changes
        mode: ErdWaterFilterMode = self.appliance.get_erd_value(ErdCode.WH_FILTER_MODE)
        if mode in [ErdWaterFilterMode.TRANSITION, ErdWaterFilterMode.UNKNOWN]:
            return mode.name.title()

        return self._converter.to_option_string(self.appliance.get_erd_value(self.erd_code))

    @property
    def options(self) -> List[str]:
        """Return a list of options"""

        #if we're transitioning or don't know what the mode is, don't allow changes
        mode: ErdWaterFilterMode = self.appliance.get_erd_value(ErdCode.WH_FILTER_MODE)
        if mode in [ErdWaterFilterMode.TRANSITION, ErdWaterFilterMode.UNKNOWN]:
            return mode.name.title()

        return self._converter.options        

    async def async_select_option(self, option: str) -> None:
        value = self._converter.from_option_string(option)
        if value in [ErdWaterFilterPosition.UNKNOWN, ErdWaterFilterPosition.READY]:
            _LOGGER.debug("Cannot set position to ready/unknown")
            return
        if self.appliance.get_erd_value(self.erd_code) != ErdWaterFilterPosition.READY:
            _LOGGER.debug("Cannot set position if not ready")
            return

        return await super().async_select_option(option)
