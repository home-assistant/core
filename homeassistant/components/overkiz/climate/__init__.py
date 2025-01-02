"""Climate entities for the Overkiz (by Somfy) integration."""

from __future__ import annotations

from enum import StrEnum, unique

from pyoverkiz.enums import Protocol
from pyoverkiz.enums.ui import UIWidget

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import OverkizDataConfigEntry
from .atlantic_electrical_heater import AtlanticElectricalHeater
from .atlantic_electrical_heater_with_adjustable_temperature_setpoint import (
    AtlanticElectricalHeaterWithAdjustableTemperatureSetpoint,
)
from .atlantic_electrical_towel_dryer import AtlanticElectricalTowelDryer
from .atlantic_heat_recovery_ventilation import AtlanticHeatRecoveryVentilation
from .atlantic_pass_apc_heat_pump_main_component import (
    AtlanticPassAPCHeatPumpMainComponent,
)
from .atlantic_pass_apc_heating_zone import AtlanticPassAPCHeatingZone
from .atlantic_pass_apc_zone_control import AtlanticPassAPCZoneControl
from .atlantic_pass_apc_zone_control_zone import AtlanticPassAPCZoneControlZone
from .hitachi_air_to_air_heat_pump_hlrrwifi import HitachiAirToAirHeatPumpHLRRWIFI
from .hitachi_air_to_air_heat_pump_ovp import HitachiAirToAirHeatPumpOVP
from .hitachi_air_to_water_heating_zone import HitachiAirToWaterHeatingZone
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
    UIWidget.HITACHI_AIR_TO_WATER_HEATING_ZONE: HitachiAirToWaterHeatingZone,
    UIWidget.SOMFY_HEATING_TEMPERATURE_INTERFACE: SomfyHeatingTemperatureInterface,
    UIWidget.SOMFY_THERMOSTAT: SomfyThermostat,
    UIWidget.VALVE_HEATING_TEMPERATURE_INTERFACE: ValveHeatingTemperatureInterface,
    UIWidget.ATLANTIC_PASS_APC_HEAT_PUMP: AtlanticPassAPCHeatPumpMainComponent,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz climate from a config entry."""
    data = entry.runtime_data

    # Match devices based on the widget.
    entities_based_on_widget: list[Entity] = [
        WIDGET_TO_CLIMATE_ENTITY[device.widget](device.device_url, data.coordinator)
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in WIDGET_TO_CLIMATE_ENTITY
    ]

    # Match devices based on the widget and controllableName.
    # ie Atlantic APC
    entities_based_on_widget_and_controllable: list[Entity] = [
        WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY[device.widget][
            device.controllable_name  # type: ignore[index]
        ](device.device_url, data.coordinator)
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY
        and device.controllable_name
        in WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY[device.widget]
    ]

    # Match devices based on the widget and protocol.
    # #ie Hitachi Air To Air Heat Pumps
    entities_based_on_widget_and_protocol: list[Entity] = [
        WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY[device.widget][device.protocol](
            device.device_url, data.coordinator
        )
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY
        and device.protocol in WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY[device.widget]
    ]

    async_add_entities(
        entities_based_on_widget
        + entities_based_on_widget_and_controllable
        + entities_based_on_widget_and_protocol
    )
