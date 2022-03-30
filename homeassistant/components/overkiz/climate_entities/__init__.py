"""Climate entities for the Overkiz (by Somfy) integration."""
from pyoverkiz.enums.ui import UIWidget

from .atlantic_electrical_heater import AtlanticElectricalHeater
from .atlantic_electrical_heater_with_adjustable_temperature_setpoint import (
    AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint,
)

WIDGET_TO_CLIMATE_ENTITY = {
    UIWidget.ATLANTIC_ELECTRICAL_HEATER: AtlanticElectricalHeater,
    UIWidget.ATLANTIC_ELECTRICAL_HEATER_WITH_ADJUSTABLE_TEMPERATURE_SETPOINT: AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint,
}
