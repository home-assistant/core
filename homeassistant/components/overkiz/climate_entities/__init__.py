"""Climate entities for the Overkiz (by Somfy) integration."""
from pyoverkiz.enums.ui import UIWidget

from .atlantic_electrical_heater import AtlanticElectricalHeater

WIDGET_TO_CLIMATE_ENTITY = {
    UIWidget.ATLANTIC_ELECTRICAL_HEATER: AtlanticElectricalHeater,
}
