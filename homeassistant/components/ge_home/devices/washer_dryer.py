import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk import ErdCode, ErdApplianceType

from .washer import WasherApi
from .dryer import DryerApi
from ..entities import GeErdSensor, GeErdBinarySensor

_LOGGER = logging.getLogger(__name__)

class WasherDryerApi(WasherApi, DryerApi):
    """API class for washer/dryer objects"""
    APPLIANCE_TYPE = ErdApplianceType.COMBINATION_WASHER_DRYER

    def get_all_entities(self) -> List[Entity]:
        base_entities = self.get_base_entities()
        
        common_entities = [
            GeErdSensor(self, ErdCode.LAUNDRY_MACHINE_STATE),
            GeErdSensor(self, ErdCode.LAUNDRY_CYCLE),
            GeErdSensor(self, ErdCode.LAUNDRY_SUB_CYCLE),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_END_OF_CYCLE),
            GeErdSensor(self, ErdCode.LAUNDRY_TIME_REMAINING),
            GeErdSensor(self, ErdCode.LAUNDRY_DELAY_TIME_REMAINING),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_DOOR),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_REMOTE_STATUS),
        ]

        washer_entities = self.get_washer_entities()
        dryer_entities = self.get_dryer_entities()

        entities = base_entities + common_entities + washer_entities + dryer_entities
        return entities

