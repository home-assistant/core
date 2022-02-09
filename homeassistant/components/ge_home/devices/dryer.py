import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk import ErdCode, ErdApplianceType

from .base import ApplianceApi
from ..entities import GeErdSensor, GeErdBinarySensor

_LOGGER = logging.getLogger(__name__)

class DryerApi(ApplianceApi):
    """API class for dryer objects"""
    APPLIANCE_TYPE = ErdApplianceType.DRYER

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        common_entities = [
            GeErdSensor(self, ErdCode.LAUNDRY_MACHINE_STATE, icon_override="mdi:tumble-dryer"),
            GeErdSensor(self, ErdCode.LAUNDRY_CYCLE, icon_override="mdi:state-machine"),
            GeErdSensor(self, ErdCode.LAUNDRY_SUB_CYCLE, icon_override="mdi:state-machine"),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_END_OF_CYCLE, icon_on_override="mdi:tumble-dryer", icon_off_override="mdi:tumble-dryer"),
            GeErdSensor(self, ErdCode.LAUNDRY_TIME_REMAINING),
            GeErdSensor(self, ErdCode.LAUNDRY_DELAY_TIME_REMAINING),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_DOOR),
            GeErdBinarySensor(self, ErdCode.LAUNDRY_REMOTE_STATUS, icon_on_override="mdi:tumble-dryer", icon_off_override="mdi:tumble-dryer"),
        ]

        dryer_entities = self.get_dryer_entities()

        entities = base_entities + common_entities + dryer_entities
        return entities

    def get_dryer_entities(self):
        #Not all options appear to exist on every dryer... we'll look for the presence of
        #a code to figure out which sensors are applicable beyond the common ones.
        dryer_entities = [         
        ]

        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_DRYNESS_LEVEL):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_DRYNESS_LEVEL)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_DRYNESSNEW_LEVEL):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_DRYNESSNEW_LEVEL)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_TEMPERATURE_OPTION):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_TEMPERATURE_OPTION)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_TEMPERATURENEW_OPTION):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_TEMPERATURENEW_OPTION)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_TUMBLE_STATUS):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_TUMBLE_STATUS)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_TUMBLENEW_STATUS):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_TUMBLENEW_STATUS)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_WASHERLINK_STATUS):
            dryer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_DRYER_WASHERLINK_STATUS)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_LEVEL_SENSOR_DISABLED):
            dryer_entities.extend([GeErdBinarySensor(self, ErdCode.LAUNDRY_DRYER_LEVEL_SENSOR_DISABLED)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_SHEET_USAGE_CONFIGURATION):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_SHEET_USAGE_CONFIGURATION)])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_SHEET_INVENTORY):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_SHEET_INVENTORY, icon_override="mdi:tray-full", uom_override="sheets")])
        if self.has_erd_code(ErdCode.LAUNDRY_DRYER_ECODRY_STATUS):
            dryer_entities.extend([GeErdSensor(self, ErdCode.LAUNDRY_DRYER_ECODRY_STATUS)])

        return dryer_entities
        
