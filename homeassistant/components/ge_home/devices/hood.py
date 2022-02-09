import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk import (
    ErdCode, 
    ErdApplianceType,
    ErdHoodFanSpeedAvailability,
    ErdHoodLightLevelAvailability,
    ErdOnOff
)

from .base import ApplianceApi
from ..entities import (
    GeHoodLightLevelSelect, 
    GeHoodFanSpeedSelect, 
    GeErdSensor, 
    GeErdSwitch, 
    ErdOnOffBoolConverter
)

_LOGGER = logging.getLogger(__name__)


class HoodApi(ApplianceApi):
    """API class for Oven Hood objects"""
    APPLIANCE_TYPE = ErdApplianceType.HOOD

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        #get the availabilities
        fan_availability: ErdHoodFanSpeedAvailability = self.try_get_erd_value(ErdCode.HOOD_FAN_SPEED_AVAILABILITY)
        light_availability: ErdHoodLightLevelAvailability = self.try_get_erd_value(ErdCode.HOOD_LIGHT_LEVEL_AVAILABILITY)
        timer_availability: ErdOnOff = self.try_get_erd_value(ErdCode.HOOD_TIMER_AVAILABILITY)

        hood_entities = [
            #looks like this is always available?
            GeErdSwitch(self, ErdCode.HOOD_DELAY_OFF, bool_converter=ErdOnOffBoolConverter(), icon_on_override="mdi:power-on", icon_off_override="mdi:power-off"),
        ]

        if fan_availability and fan_availability.is_available:
            hood_entities.append(GeHoodFanSpeedSelect(self, ErdCode.HOOD_FAN_SPEED))
        #for now, represent as a select
        if light_availability and light_availability.is_available:
            hood_entities.append(GeHoodLightLevelSelect(self, ErdCode.HOOD_LIGHT_LEVEL))
        if timer_availability == ErdOnOff.ON:
            hood_entities.append(GeErdSensor(self, ErdCode.HOOD_TIMER))

        entities = base_entities + hood_entities
        return entities
        
