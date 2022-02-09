import abc
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import (
    TEMP_FAHRENHEIT,
    TEMP_CELSIUS
)
from gehomesdk import ErdCode, ErdMeasurementUnits
from ...const import DOMAIN
from .ge_erd_entity import GeEntity

_LOGGER = logging.getLogger(__name__)

class GeWaterHeater(GeEntity, WaterHeaterEntity, metaclass=abc.ABCMeta):
    """Mock temperature/operation mode supporting device as a water heater"""

    @property
    def heater_type(self) -> str:
        raise NotImplementedError

    @property
    def operation_list(self) -> List[str]:
        raise NotImplementedError

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.serial_or_mac}_{self.heater_type}"

    @property
    def name(self) -> Optional[str]:
        return f"{self.serial_or_mac} {self.heater_type.title()}"

    @property
    def temperature_unit(self):
        measurement_system = self.appliance.get_erd_value(ErdCode.TEMPERATURE_UNIT)
        if measurement_system == ErdMeasurementUnits.METRIC:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def supported_features(self):
        raise NotImplementedError
