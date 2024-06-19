"""Climate entities for the Overkiz (by Somfy) integration."""

from enum import StrEnum, unique

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
from .atlantic_pass_apc_zone_control_zone import AtlanticPassAPCZoneControlZone
from .hitachi_air_to_air_heat_pump_hlrrwifi import HitachiAirToAirHeatPumpHLRRWIFI
from .hitachi_air_to_air_heat_pump_ovp import HitachiAirToAirHeatPumpOVP
from .somfy_heating_temperature_interface import SomfyHeatingTemperatureInterface
from .somfy_thermostat import SomfyThermostat
from .valve_heating_temperature_interface import ValveHeatingTemperatureInterface


@unique
class Controllable(StrEnum):
    """Enum for widget controllables."""

    IO_ATLANTIC_PASS_APC_HEATING_AND_COOLING_ZONE = (
        "io:AtlanticPassAPCHeatingAndCoolingZoneComponent"
    )
    IO_ATLANTIC_PASS_APC_ZONE_CONTROL_ZONE = (
        "io:AtlanticPassAPCZoneControlZoneComponent"
    )


WIDGET_TO_CLIMATE_ENTITY = {
    UIWidget.ATLANTIC_ELECTRICAL_HEATER: AtlanticElectricalHeater,
    UIWidget.ATLANTIC_ELECTRICAL_HEATER_WITH_ADJUSTABLE_TEMPERATURE_SETPOINT: AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint,
    UIWidget.ATLANTIC_ELECTRICAL_TOWEL_DRYER: AtlanticElectricalTowelDryer,
    UIWidget.ATLANTIC_HEAT_RECOVERY_VENTILATION: AtlanticHeatRecoveryVentilation,
    UIWidget.ATLANTIC_PASS_APC_HEATING_ZONE: AtlanticPassAPCHeatingZone,
    UIWidget.ATLANTIC_PASS_APC_ZONE_CONTROL: AtlanticPassAPCZoneControl,
    UIWidget.SOMFY_HEATING_TEMPERATURE_INTERFACE: SomfyHeatingTemperatureInterface,
    UIWidget.SOMFY_THERMOSTAT: SomfyThermostat,
    UIWidget.VALVE_HEATING_TEMPERATURE_INTERFACE: ValveHeatingTemperatureInterface,
}

# For Atlantic APC, some devices are standalone and control themselves, some others needs to be
# managed by a ZoneControl device. Widget name is the same in the two cases.
WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY = {
    UIWidget.ATLANTIC_PASS_APC_HEATING_AND_COOLING_ZONE: {
        Controllable.IO_ATLANTIC_PASS_APC_HEATING_AND_COOLING_ZONE: AtlanticPassAPCHeatingZone,
        Controllable.IO_ATLANTIC_PASS_APC_ZONE_CONTROL_ZONE: AtlanticPassAPCZoneControlZone,
    }
}

# Hitachi air-to-air heatpumps come in 2 flavors (HLRRWIFI and OVP) that are separated in 2 classes
WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY = {
    UIWidget.HITACHI_AIR_TO_AIR_HEAT_PUMP: {
        Protocol.HLRR_WIFI: HitachiAirToAirHeatPumpHLRRWIFI,
        Protocol.OVP: HitachiAirToAirHeatPumpOVP,
    },
}
