import logging
from typing import Optional
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT

from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_TIMESTAMP,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
#from homeassistant.components.sensor import (
#    STATE_CLASS_MEASUREMENT,
#    STATE_CLASS_TOTAL_INCREASING
#)
# For now, let's not force the newer version, we'll use the same constants
# but it'll be optional.
# TODO: Force the usage of new HA
STATE_CLASS_MEASUREMENT = "measurement"
STATE_CLASS_TOTAL_INCREASING = 'total_increasing'

from homeassistant.helpers.entity import Entity
from gehomesdk import ErdCode, ErdCodeType, ErdCodeClass, ErdMeasurementUnits

from .ge_erd_entity import GeErdEntity
from ...devices import ApplianceApi

_LOGGER = logging.getLogger(__name__)

class GeErdSensor(GeErdEntity, Entity):
    """GE Entity for sensors"""

    def __init__(
        self, 
        api: ApplianceApi, 
        erd_code: ErdCodeType, 
        erd_override: str = None, 
        icon_override: str = None, 
        device_class_override: str = None,
        state_class_override: str = None,
        uom_override: str = None,
    ):
        super().__init__(api, erd_code, erd_override, icon_override, device_class_override)
        self._uom_override = uom_override
        self._state_class_override = state_class_override

    @property
    def state(self) -> Optional[str]:
        try:
            value = self.appliance.get_erd_value(self.erd_code)
        except KeyError:
            return None
        # TODO: perhaps enhance so that there's a list of variables available
        #       for the stringify function to consume...
        return self._stringify(value, temp_units=self._temp_units)

    @property
    def unit_of_measurement(self) -> Optional[str]:
        return self._get_uom()

    @property
    def state_class(self) -> Optional[str]:
        return self._get_state_class()

    @property
    def _temp_units(self) -> Optional[str]:
        if self._measurement_system == ErdMeasurementUnits.METRIC:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    def _get_uom(self):
        """Select appropriate units"""
        
        #if we have an override, just use it
        if self._uom_override:
            return self._uom_override

        if (
            self.erd_code_class
            in [ErdCodeClass.RAW_TEMPERATURE, ErdCodeClass.NON_ZERO_TEMPERATURE]
            or self.device_class == DEVICE_CLASS_TEMPERATURE
        ):
            return self._temp_units
        if (
            self.erd_code_class == ErdCodeClass.BATTERY
            or self.device_class == DEVICE_CLASS_BATTERY
        ):
            return "%"
        if self.erd_code_class == ErdCodeClass.PERCENTAGE:
            return "%"
        if self.device_class == DEVICE_CLASS_POWER_FACTOR:
            return "%"
        if self.erd_code_class == ErdCodeClass.FLOW_RATE:
            if self._measurement_system == ErdMeasurementUnits.METRIC:
                return "lpm"
            return "gpm" 
        if self.erd_code_class == ErdCodeClass.LIQUID_VOLUME:       
            if self._measurement_system == ErdMeasurementUnits.METRIC:
                return "l"
            return "g"
        return None

    def _get_device_class(self) -> Optional[str]:
        if self._device_class_override:
            return self._device_class_override
        if self.erd_code_class in [
            ErdCodeClass.RAW_TEMPERATURE,
            ErdCodeClass.NON_ZERO_TEMPERATURE,
        ]:
            return DEVICE_CLASS_TEMPERATURE
        if self.erd_code_class == ErdCodeClass.BATTERY:
            return DEVICE_CLASS_BATTERY
        if self.erd_code_class == ErdCodeClass.POWER:
            return DEVICE_CLASS_POWER
        if self.erd_code_class == ErdCodeClass.ENERGY:
            return DEVICE_CLASS_ENERGY

        return None

    def _get_state_class(self) -> Optional[str]:
        if self._state_class_override:
            return self._state_class_override

        if self.device_class in [DEVICE_CLASS_TEMPERATURE, DEVICE_CLASS_ENERGY]:
            return STATE_CLASS_MEASUREMENT
        if self.erd_code_class in [ErdCodeClass.FLOW_RATE, ErdCodeClass.PERCENTAGE]:
            return STATE_CLASS_MEASUREMENT
        if self.erd_code_class in [ErdCodeClass.LIQUID_VOLUME]:
            return STATE_CLASS_TOTAL_INCREASING
        
        return None

    def _get_icon(self):
        if self.erd_code_class == ErdCodeClass.DOOR:
            if self.state.lower().endswith("open"):
                return "mdi:door-open"
            if self.state.lower().endswith("closed"):
                return "mdi:door-closed"
        return super()._get_icon()

    async def set_value(self, value):
        """Sets the ERD value, assumes that the data type is correct"""
        try:
            await self.appliance.async_set_erd_value(self.erd_code, value) 
        except:
            _LOGGER.warning(f"Could not set {self.name} to {value}")