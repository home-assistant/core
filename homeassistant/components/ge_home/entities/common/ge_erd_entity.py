from datetime import timedelta
from typing import Optional

from gehomesdk import ErdCode, ErdCodeType, ErdCodeClass, ErdMeasurementUnits

from ...const import DOMAIN
from ...devices import ApplianceApi
from .ge_entity import GeEntity


class GeErdEntity(GeEntity):
    """Parent class for GE entities tied to a specific ERD"""

    def __init__(
        self,
        api: ApplianceApi,
        erd_code: ErdCodeType,
        erd_override: str = None,
        icon_override: str = None,
        device_class_override: str = None,
    ):
        super().__init__(api)
        self._erd_code = api.appliance.translate_erd_code(erd_code)
        self._erd_code_class = api.appliance.get_erd_code_class(self._erd_code)
        self._erd_override = erd_override
        self._icon_override = icon_override
        self._device_class_override = device_class_override

        if not self._erd_code_class:
            self._erd_code_class = ErdCodeClass.GENERAL

    @property
    def erd_code(self) -> ErdCodeType:
        return self._erd_code

    @property
    def erd_code_class(self) -> ErdCodeClass:
        return self._erd_code_class

    @property
    def erd_string(self) -> str:
        erd_code = self.erd_code
        if isinstance(self.erd_code, ErdCode):
            return erd_code.name
        return erd_code

    @property
    def name(self) -> Optional[str]:
        erd_string = self.erd_string

        # override the name if specified
        if self._erd_override != None:
            erd_string = self._erd_override

        erd_title = " ".join(erd_string.split("_")).title()
        return f"{self.serial_or_mac} {erd_title}"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{DOMAIN}_{self.serial_or_mac}_{self.erd_string.lower()}"

    def _stringify(self, value: any, **kwargs) -> Optional[str]:
        """Stringify a value"""
        # perform special processing before passing over to the default method
        if self.erd_code == ErdCode.CLOCK_TIME:
            return value.strftime("%H:%M:%S") if value else None
        if self.erd_code_class == ErdCodeClass.RAW_TEMPERATURE:
            return f"{value}"
        if self.erd_code_class == ErdCodeClass.NON_ZERO_TEMPERATURE:
            return f"{value}" if value else ""
        if self.erd_code_class == ErdCodeClass.TIMER or isinstance(value, timedelta):
            return str(value)[:-3] if value else "Off"
        if value is None:
            return None
        return self.appliance.stringify_erd_value(value, **kwargs)

    @property
    def _measurement_system(self) -> Optional[ErdMeasurementUnits]:
        """
        Get the measurement system this appliance is using.  For now, uses the
        temperature unit if available, otherwise assumes imperial.
        """
        try:
            value = self.appliance.get_erd_value(ErdCode.TEMPERATURE_UNIT)
        except KeyError:
            return None
        return value

    def _get_icon(self):
        """Select an appropriate icon."""

        if self._icon_override:
            return self._icon_override
        if not isinstance(self.erd_code, ErdCode):
            return None
        if self.erd_code_class == ErdCodeClass.CLOCK:
            return "mdi:clock"
        if self.erd_code_class == ErdCodeClass.COUNTER:
            return "mdi:counter"
        if self.erd_code_class == ErdCodeClass.DOOR:
            return "mdi:door"
        if self.erd_code_class == ErdCodeClass.TIMER:
            return "mdi:timer-outline"
        if self.erd_code_class == ErdCodeClass.LOCK_CONTROL:
            return "mdi:lock-outline"
        if self.erd_code_class == ErdCodeClass.SABBATH_CONTROL:
            return "mdi:judaism"
        if self.erd_code_class == ErdCodeClass.COOLING_CONTROL:
            return "mdi:snowflake"
        if self.erd_code_class == ErdCodeClass.OVEN_SENSOR:
            return "mdi:stove"
        if self.erd_code_class == ErdCodeClass.FRIDGE_SENSOR:
            return "mdi:fridge-bottom"
        if self.erd_code_class == ErdCodeClass.FREEZER_SENSOR:
            return "mdi:fridge-top"
        if self.erd_code_class == ErdCodeClass.DISPENSER_SENSOR:
            return "mdi:cup-water"
        if self.erd_code_class == ErdCodeClass.DISHWASHER_SENSOR:
            return "mdi:dishwasher"
        if self.erd_code_class == ErdCodeClass.WATERFILTER_SENSOR:
            return "mdi:water"
        if self.erd_code_class == ErdCodeClass.LAUNDRY_SENSOR:
            return "mdi:washing-machine"
        if self.erd_code_class == ErdCodeClass.LAUNDRY_WASHER_SENSOR:
            return "mdi:washing-machine"
        if self.erd_code_class == ErdCodeClass.LAUNDRY_DRYER_SENSOR:
            return "mdi:tumble-dryer"          
        if self.erd_code_class == ErdCodeClass.ADVANTIUM_SENSOR:
            return "mdi:microwave"              
        if self.erd_code_class == ErdCodeClass.FLOW_RATE:
            return "mdi:water"   
        if self.erd_code_class == ErdCodeClass.LIQUID_VOLUME:
            return "mdi:water" 
        if self.erd_code_class == ErdCodeClass.AC_SENSOR:
            return "mdi:air-conditioner"    
        if self.erd_code_class == ErdCodeClass.TEMPERATURE_CONTROL:
            return "mdi:thermometer"   
        if self.erd_code_class == ErdCodeClass.FAN:
            return "mdi:fan"
        if self.erd_code_class == ErdCodeClass.LIGHT:
            return "mdi:lightbulb"         

        return None
