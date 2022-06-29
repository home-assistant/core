"""Climate entities for the Overkiz (by Somfy) integration."""
from pyoverkiz.enums.ui import UIWidget

from .atlantic_electrical_heater import AtlanticElectricalHeater
from .atlantic_electrical_towel_dryer import AtlanticElectricalTowelDryer
from .atlantic_pass_apc_zone_control import AtlanticPassAPCZoneControl
from .somfy_thermostat import SomfyThermostat

WIDGET_TO_CLIMATE_ENTITY = {
    UIWidget.ATLANTIC_ELECTRICAL_HEATER: AtlanticElectricalHeater,
    UIWidget.ATLANTIC_ELECTRICAL_TOWEL_DRYER: AtlanticElectricalTowelDryer,
    UIWidget.ATLANTIC_PASS_APC_ZONE_CONTROL: AtlanticPassAPCZoneControl,
    UIWidget.SOMFY_THERMOSTAT: SomfyThermostat,
}
