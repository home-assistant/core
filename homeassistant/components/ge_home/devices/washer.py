import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk import ErdCode, ErdApplianceType

from .base import ApplianceApi
from ..entities import GeErdSensor, GeErdBinarySensor, GeErdPropertySensor

_LOGGER = logging.getLogger(__name__)


class WasherApi(ApplianceApi):
    """API class for washer objects"""
    APPLIANCE_TYPE = ErdApplianceType.WASHER

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        common_entities = [
            GeErdSensor(self, ErdCode.LAUNDRY_MACHINE_STATE),
            GeErdSensor(self, ErdCode.LAUNDRY_CYCLE, icon_override="mdi:state-machine"),
            GeErdSensor(self, ErdCode.LAUNDRY_SUB_CYCLE, icon_override="mdi:state-machine"),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_END_OF_CYCLE),
            GeErdSensor(self, ErdCode.LAUNDRY_TIME_REMAINING),
            GeErdSensor(self, ErdCode.LAUNDRY_DELAY_TIME_REMAINING),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_DOOR),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_REMOTE_STATUS),
        ]

        washer_entities = self.get_washer_entities()      

        entities = base_entities + common_entities + washer_entities
        return entities
        
    def get_washer_entities(self) -> List[Entity]:
        washer_entities = [         
            GeErdSensor(self, ErdCode.LAUNDRY_WASHER_SOIL_LEVEL, icon_override="mdi:emoticon-poop"),
            GeErdSensor(self, ErdCode.LAUNDRY_WASHER_WASHTEMP_LEVEL),
            GeErdSensor(self, ErdCode.LAUNDRY_WASHER_SPINTIME_LEVEL, icon_override="mdi:speedometer"),
            GeErdSensor(self, ErdCode.LAUNDRY_WASHER_RINSE_OPTION, icon_override="mdi:shimmer"),
        ]

        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_DOOR_LOCK):
            washer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_WASHER_DOOR_LOCK)])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_TANK_STATUS):
            washer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_WASHER_TANK_STATUS)])           
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_TANK_SELECTED):
            washer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_WASHER_TANK_SELECTED)])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_TIMESAVER):
            washer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_WASHER_TIMESAVER, icon_on_override="mdi:sort-clock-ascending", icon_off_override="mdi:sort-clock-ascending-outline")])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_POWERSTEAM):
            washer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_WASHER_POWERSTEAM, icon_on_override="mdi:kettle-steam", icon_off_override="mdi:kettle-steam-outline")])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_PREWASH):
            washer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_WASHER_PREWASH, icon_on_override="mdi:water-plus", icon_off_override="mdi:water-remove-outline")])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_TUMBLECARE):
            washer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_WASHER_TUMBLECARE)])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_SMART_DISPENSE):
            washer_entities.extend([GeErdPropertySensor(self, ErdCode.LAUNDRY_WASHER_SMART_DISPENSE, "loads_left", uom_override="loads")])
        if self.has_erd_code(ErdCode.LAUNDRY_WASHER_SMART_DISPENSE_TANK_STATUS):
            washer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_WASHER_SMART_DISPENSE_TANK_STATUS)])

        return washer_entities
