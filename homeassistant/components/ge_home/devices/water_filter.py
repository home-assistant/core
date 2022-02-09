import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk import ErdCode, ErdApplianceType

from .base import ApplianceApi
from ..entities import (
    GeErdSensor,
    GeErdBinarySensor,
    GeErdFilterPositionSelect,
)

_LOGGER = logging.getLogger(__name__)


class WaterFilterApi(ApplianceApi):
    """API class for water filter objects"""

    APPLIANCE_TYPE = ErdApplianceType.POE_WATER_FILTER

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        wf_entities = [
            GeErdSensor(self, ErdCode.WH_FILTER_MODE),
            GeErdSensor(self, ErdCode.WH_FILTER_VALVE_STATE, icon_override="mdi:state-machine"),
            GeErdFilterPositionSelect(self, ErdCode.WH_FILTER_POSITION),
            GeErdBinarySensor(self, ErdCode.WH_FILTER_MANUAL_MODE, icon_on_override="mdi:human", icon_off_override="mdi:robot"),
            GeErdBinarySensor(self, ErdCode.WH_FILTER_LEAK_VALIDITY, device_class_override="moisture"),
            GeErdSensor(self, ErdCode.WH_FILTER_FLOW_RATE),
            GeErdSensor(self, ErdCode.WH_FILTER_DAY_USAGE),
            GeErdSensor(self, ErdCode.WH_FILTER_LIFE_REMAINING),
            GeErdBinarySensor(self, ErdCode.WH_FILTER_FLOW_ALERT, device_class_override="moisture"),
        ]
        entities = base_entities + wf_entities
        return entities
