import logging
from typing import List

from homeassistant.helpers.entity import Entity
from gehomesdk.erd import ErdCode, ErdApplianceType

from .base import ApplianceApi
from ..entities import GeAdvantium, GeErdSensor, GeErdBinarySensor, GeErdPropertySensor, GeErdPropertyBinarySensor, UPPER_OVEN

_LOGGER = logging.getLogger(__name__)

class AdvantiumApi(ApplianceApi):
    """API class for Advantium objects"""
    APPLIANCE_TYPE = ErdApplianceType.ADVANTIUM

    def get_all_entities(self) -> List[Entity]:
        base_entities = super().get_all_entities()

        advantium_entities = [
            GeErdSensor(self, ErdCode.UNIT_TYPE),
            GeErdBinarySensor(self, ErdCode.UPPER_OVEN_REMOTE_ENABLED, self._single_name(ErdCode.UPPER_OVEN_REMOTE_ENABLED)),
            GeErdBinarySensor(self, ErdCode.MICROWAVE_REMOTE_ENABLE),
            GeErdSensor(self, ErdCode.UPPER_OVEN_DISPLAY_TEMPERATURE, self._single_name(ErdCode.UPPER_OVEN_DISPLAY_TEMPERATURE)),
            GeErdSensor(self, ErdCode.ADVANTIUM_KITCHEN_TIME_REMAINING),
            GeErdSensor(self, ErdCode.ADVANTIUM_COOK_TIME_REMAINING),
            GeAdvantium(self),

            #Cook Status
            GeErdPropertySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "cook_mode"),
            GeErdPropertySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "termination_reason", icon_override="mdi:information-outline"),
            GeErdPropertySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "preheat_status", icon_override="mdi:fire"),
            GeErdPropertySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "temperature", icon_override="mdi:thermometer"),
            GeErdPropertySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "power_level", icon_override="mdi:gauge"),
            GeErdPropertySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "warm_status", icon_override="mdi:radiator"),
            GeErdPropertyBinarySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "door_status", device_class_override="door"),
            GeErdPropertyBinarySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "sensing_active", icon_on_override="mdi:flash-auto", icon_off_override="mdi:flash-off"),
            GeErdPropertyBinarySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "cooling_fan_status", icon_on_override="mdi:fan", icon_off_override="mdi:fan-off"),
            GeErdPropertyBinarySensor(self, ErdCode.ADVANTIUM_COOK_STATUS, "oven_light_status", icon_on_override="mdi:lightbulb-on", icon_off_override="mdi:lightbulb-off"),
        ]
        entities = base_entities + advantium_entities
        return entities

    def _single_name(self, erd_code: ErdCode):
        return erd_code.name.replace(UPPER_OVEN+"_","").replace("_", " ").title()

