from typing import Optional

import magicattr
from gehomesdk import ErdCode, ErdCodeType, ErdMeasurementUnits
from ...devices import ApplianceApi
from .ge_erd_sensor import GeErdSensor


class GeErdPropertySensor(GeErdSensor):
    """GE Entity for sensors"""
    def __init__(   
        self, api: ApplianceApi, erd_code: ErdCodeType, erd_property: str, 
        erd_override: str = None, icon_override: str = None, device_class_override: str = None, 
        state_class_override: str = None, uom_override: str = None
    ):
        super().__init__(
            api, erd_code, erd_override=erd_override, 
            icon_override=icon_override, device_class_override=device_class_override, 
            state_class_override=state_class_override,
            uom_override=uom_override
        )
        self.erd_property = erd_property
        self._erd_property_cleansed = erd_property.replace(".","_").replace("[","_").replace("]","_")

    @property
    def unique_id(self) -> Optional[str]:
        return f"{super().unique_id}_{self._erd_property_cleansed}"

    @property
    def name(self) -> Optional[str]:
        base_string = super().name
        property_name = self._erd_property_cleansed.replace("_", " ").title()
        return f"{base_string} {property_name}"

    @property
    def state(self) -> Optional[str]:
        try:
            value = magicattr.get(self.appliance.get_erd_value(self.erd_code), self.erd_property)
        except KeyError:
            return None
        return self._stringify(value, temp_units=self._temp_units)
