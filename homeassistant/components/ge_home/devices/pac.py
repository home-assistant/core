import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk.erd import ErdCode, ErdApplianceType

from .base import ApplianceApi
from ..entities import GePacClimate, GeErdSensor, GeErdSwitch, ErdOnOffBoolConverter

_LOGGER = logging.getLogger(__name__)


class PacApi(ApplianceApi):
    """API class for Portable AC objects"""
    APPLIANCE_TYPE = ErdApplianceType.PORTABLE_AIR_CONDITIONER

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        pac_entities = [
            GePacClimate(self),
            GeErdSensor(self, ErdCode.AC_TARGET_TEMPERATURE),
            GeErdSensor(self, ErdCode.AC_AMBIENT_TEMPERATURE),
            GeErdSensor(self, ErdCode.AC_FAN_SETTING, icon_override="mdi:fan"),
            GeErdSensor(self, ErdCode.AC_OPERATION_MODE),
            GeErdSwitch(self, ErdCode.AC_POWER_STATUS, bool_converter=ErdOnOffBoolConverter(), icon_on_override="mdi:power-on", icon_off_override="mdi:power-off"),
        ]

        entities = base_entities + pac_entities
        return entities
        
