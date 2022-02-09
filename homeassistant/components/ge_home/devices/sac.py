import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk.erd import ErdCode, ErdApplianceType

from .base import ApplianceApi
from ..entities import GeSacClimate, GeSacTemperatureSensor, GeErdSensor, GeErdSwitch, ErdOnOffBoolConverter

_LOGGER = logging.getLogger(__name__)


class SacApi(ApplianceApi):
    """API class for Split AC objects"""
    APPLIANCE_TYPE = ErdApplianceType.SPLIT_AIR_CONDITIONER

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        sac_entities = [
            GeSacClimate(self),
            GeSacTemperatureSensor(self, ErdCode.AC_TARGET_TEMPERATURE),
            GeSacTemperatureSensor(self, ErdCode.AC_AMBIENT_TEMPERATURE),
            GeErdSensor(self, ErdCode.AC_FAN_SETTING, icon_override="mdi:fan"),
            GeErdSensor(self, ErdCode.AC_OPERATION_MODE),
            GeErdSwitch(self, ErdCode.AC_POWER_STATUS, bool_converter=ErdOnOffBoolConverter(), icon_on_override="mdi:power-on", icon_off_override="mdi:power-off"),
        ]

        if self.has_erd_code(ErdCode.SAC_SLEEP_MODE):
            sac_entities.append(GeErdSwitch(self, ErdCode.SAC_SLEEP_MODE, bool_converter=ErdOnOffBoolConverter(), icon_on_override="mdi:sleep", icon_off_override="mdi:sleep-off"))
        if self.has_erd_code(ErdCode.SAC_AUTO_SWING_MODE):
            sac_entities.append(GeErdSwitch(self, ErdCode.SAC_AUTO_SWING_MODE, bool_converter=ErdOnOffBoolConverter(), icon_on_override="mdi:arrow-decision-auto", icon_off_override="mdi:arrow-decision-auto-outline"))


        entities = base_entities + sac_entities
        return entities
        
