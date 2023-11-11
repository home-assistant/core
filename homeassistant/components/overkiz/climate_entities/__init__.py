"""Climate entities for the Overkiz (by Somfy) integration."""
from pyoverkiz.enums import Protocol
from pyoverkiz.enums.ui import UIWidget

from .atlantic_electrical_heater import AtlanticElectricalHeater
from .atlantic_electrical_heater_with_adjustable_temperature_setpoint import (
    AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint,
)
from .atlantic_electrical_towel_dryer import AtlanticElectricalTowelDryer
from .atlantic_heat_recovery_ventilation import AtlanticHeatRecoveryVentilation
from .atlantic_pass_apc_heating_zone import AtlanticPassAPCHeatingZone
from .atlantic_pass_apc_zone_control import AtlanticPassAPCZoneControl
from .hitachi_air_to_air_heat_pump_hlrrwifi import HitachiAirToAirHeatPumpHLRRWIFI
from .somfy_heating_temperature_interface import SomfyHeatingTemperatureInterface
from .somfy_thermostat import SomfyThermostat
from .valve_heating_temperature_interface import ValveHeatingTemperatureInterface

WIDGET_TO_CLIMATE_ENTITY = {
    UIWidget.ATLANTIC_ELECTRICAL_HEATER: AtlanticElectricalHeater,
    UIWidget.ATLANTIC_ELECTRICAL_HEATER_WITH_ADJUSTABLE_TEMPERATURE_SETPOINT: AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint,
    UIWidget.ATLANTIC_ELECTRICAL_TOWEL_DRYER: AtlanticElectricalTowelDryer,
    UIWidget.ATLANTIC_HEAT_RECOVERY_VENTILATION: AtlanticHeatRecoveryVentilation,
    # ATLANTIC_PASS_APC_HEATING_AND_COOLING_ZONE works exactly the same as ATLANTIC_PASS_APC_HEATING_ZONE
    UIWidget.ATLANTIC_PASS_APC_HEATING_AND_COOLING_ZONE: AtlanticPassAPCHeatingZone,
    UIWidget.ATLANTIC_PASS_APC_HEATING_ZONE: AtlanticPassAPCHeatingZone,
    UIWidget.ATLANTIC_PASS_APC_ZONE_CONTROL: AtlanticPassAPCZoneControl,
    UIWidget.SOMFY_HEATING_TEMPERATURE_INTERFACE: SomfyHeatingTemperatureInterface,
    UIWidget.SOMFY_THERMOSTAT: SomfyThermostat,
    UIWidget.VALVE_HEATING_TEMPERATURE_INTERFACE: ValveHeatingTemperatureInterface,
}

# Hitachi air-to-air heatpumps come in 2 flavors (HLRRWIFI and OVP) that are separated in 2 classes
WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY = {
    UIWidget.HITACHI_AIR_TO_AIR_HEAT_PUMP: {
        Protocol.HLRR_WIFI: HitachiAirToAirHeatPumpHLRRWIFI,
    },
}
