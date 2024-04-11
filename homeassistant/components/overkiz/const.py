"""Constants for the Overkiz (by Somfy) integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from pyoverkiz.enums import (
    MeasuredValueType,
    OverkizCommandParam,
    Server,
    UIClass,
    UIWidget,
)

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

DOMAIN: Final = "overkiz"
LOGGER: logging.Logger = logging.getLogger(__package__)

CONF_API_TYPE: Final = "api_type"
CONF_HUB: Final = "hub"
DEFAULT_SERVER: Final = Server.SOMFY_EUROPE
DEFAULT_HOST: Final = "gateway-xxxx-xxxx-xxxx.local:8443"

UPDATE_INTERVAL: Final = timedelta(seconds=30)
UPDATE_INTERVAL_ALL_ASSUMED_STATE: Final = timedelta(minutes=60)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

IGNORED_OVERKIZ_DEVICES: list[UIClass | UIWidget] = [
    UIClass.PROTOCOL_GATEWAY,
    UIClass.POD,
]

# Used to map the Somfy widget and ui_class to the Home Assistant platform
OVERKIZ_DEVICE_TO_PLATFORM: dict[UIClass | UIWidget, Platform | None] = {
    UIClass.ADJUSTABLE_SLATS_ROLLER_SHUTTER: Platform.COVER,
    UIClass.AWNING: Platform.COVER,
    UIClass.CURTAIN: Platform.COVER,
    UIClass.DOOR_LOCK: Platform.LOCK,
    UIClass.EXTERIOR_SCREEN: Platform.COVER,
    UIClass.EXTERIOR_VENETIAN_BLIND: Platform.COVER,
    UIClass.GARAGE_DOOR: Platform.COVER,
    UIClass.GATE: Platform.COVER,
    UIClass.LIGHT: Platform.LIGHT,
    UIClass.ON_OFF: Platform.SWITCH,
    UIClass.PERGOLA: Platform.COVER,
    UIClass.ROLLER_SHUTTER: Platform.COVER,
    UIClass.SCREEN: Platform.COVER,
    UIClass.SHUTTER: Platform.COVER,
    UIClass.SIREN: Platform.SIREN,
    UIClass.SWIMMING_POOL: Platform.SWITCH,
    UIClass.SWINGING_SHUTTER: Platform.COVER,
    UIClass.VENETIAN_BLIND: Platform.COVER,
    UIClass.WINDOW: Platform.COVER,
    UIWidget.ALARM_PANEL_CONTROLLER: Platform.ALARM_CONTROL_PANEL,  # widgetName, uiClass is Alarm (not supported)
    UIWidget.ATLANTIC_ELECTRICAL_HEATER: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.ATLANTIC_ELECTRICAL_HEATER_WITH_ADJUSTABLE_TEMPERATURE_SETPOINT: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.ATLANTIC_ELECTRICAL_TOWEL_DRYER: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.ATLANTIC_HEAT_RECOVERY_VENTILATION: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.ATLANTIC_PASS_APC_DHW: Platform.WATER_HEATER,  # widgetName, uiClass is WaterHeatingSystem (not supported)
    UIWidget.ATLANTIC_PASS_APC_HEATING_AND_COOLING_ZONE: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.ATLANTIC_PASS_APC_HEATING_ZONE: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.ATLANTIC_PASS_APC_ZONE_CONTROL: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.DOMESTIC_HOT_WATER_PRODUCTION: Platform.WATER_HEATER,  # widgetName, uiClass is WaterHeatingSystem (not supported)
    UIWidget.DOMESTIC_HOT_WATER_TANK: Platform.SWITCH,  # widgetName, uiClass is WaterHeatingSystem (not supported)
    UIWidget.HITACHI_AIR_TO_AIR_HEAT_PUMP: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.HITACHI_DHW: Platform.WATER_HEATER,  # widgetName, uiClass is HitachiHeatingSystem (not supported)
    UIWidget.MY_FOX_ALARM_CONTROLLER: Platform.ALARM_CONTROL_PANEL,  # widgetName, uiClass is Alarm (not supported)
    UIWidget.MY_FOX_SECURITY_CAMERA: Platform.SWITCH,  # widgetName, uiClass is Camera (not supported)
    UIWidget.RTD_INDOOR_SIREN: Platform.SWITCH,  # widgetName, uiClass is Siren (not supported)
    UIWidget.RTD_OUTDOOR_SIREN: Platform.SWITCH,  # widgetName, uiClass is Siren (not supported)
    UIWidget.RTS_GENERIC: Platform.COVER,  # widgetName, uiClass is Generic (not supported)
    UIWidget.SIREN_STATUS: None,  # widgetName, uiClass is Siren (siren)
    UIWidget.SOMFY_HEATING_TEMPERATURE_INTERFACE: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.SOMFY_THERMOSTAT: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    UIWidget.STATELESS_ALARM_CONTROLLER: Platform.SWITCH,  # widgetName, uiClass is Alarm (not supported)
    UIWidget.STATEFUL_ALARM_CONTROLLER: Platform.ALARM_CONTROL_PANEL,  # widgetName, uiClass is Alarm (not supported)
    UIWidget.STATELESS_EXTERIOR_HEATING: Platform.SWITCH,  # widgetName, uiClass is ExteriorHeatingSystem (not supported)
    UIWidget.TSKALARM_CONTROLLER: Platform.ALARM_CONTROL_PANEL,  # widgetName, uiClass is Alarm (not supported)
    UIWidget.VALVE_HEATING_TEMPERATURE_INTERFACE: Platform.CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
}

# Map Overkiz camelCase to Home Assistant snake_case for translation
OVERKIZ_STATE_TO_TRANSLATION: dict[str, str] = {
    OverkizCommandParam.EXTERNAL_GATEWAY: "external_gateway",
    OverkizCommandParam.LOCAL_USER: "local_user",
    OverkizCommandParam.LOW_BATTERY: "low_battery",
    OverkizCommandParam.LSC: "lsc",
    OverkizCommandParam.MAINTENANCE_REQUIRED: "maintenance_required",
    OverkizCommandParam.NO_DEFECT: "no_defect",
    OverkizCommandParam.SAAC: "saac",
    OverkizCommandParam.SFC: "sfc",
    OverkizCommandParam.UPS: "ups",
}

OVERKIZ_UNIT_TO_HA: dict[str, str] = {
    MeasuredValueType.ABSOLUTE_VALUE: "",
    MeasuredValueType.ANGLE_IN_DEGREES: DEGREE,
    MeasuredValueType.ANGULAR_SPEED_IN_DEGREES_PER_SECOND: f"{DEGREE}/{UnitOfTime.SECONDS}",
    MeasuredValueType.ELECTRICAL_ENERGY_IN_KWH: UnitOfEnergy.KILO_WATT_HOUR,
    MeasuredValueType.ELECTRICAL_ENERGY_IN_WH: UnitOfEnergy.WATT_HOUR,
    MeasuredValueType.ELECTRICAL_POWER_IN_KW: UnitOfPower.KILO_WATT,
    MeasuredValueType.ELECTRICAL_POWER_IN_W: UnitOfPower.WATT,
    MeasuredValueType.ELECTRIC_CURRENT_IN_AMPERE: UnitOfElectricCurrent.AMPERE,
    MeasuredValueType.ELECTRIC_CURRENT_IN_MILLI_AMPERE: UnitOfElectricCurrent.MILLIAMPERE,
    MeasuredValueType.ENERGY_IN_CAL: "cal",
    MeasuredValueType.ENERGY_IN_KCAL: "kcal",
    MeasuredValueType.FLOW_IN_LITRE_PER_SECOND: f"{UnitOfVolume.LITERS}/{UnitOfTime.SECONDS}",
    MeasuredValueType.FLOW_IN_METER_CUBE_PER_HOUR: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    MeasuredValueType.FLOW_IN_METER_CUBE_PER_SECOND: f"{UnitOfVolume.CUBIC_METERS}/{UnitOfTime.SECONDS}",
    MeasuredValueType.FOSSIL_ENERGY_IN_WH: UnitOfEnergy.WATT_HOUR,
    MeasuredValueType.GRADIENT_IN_PERCENTAGE_PER_SECOND: f"{PERCENTAGE}/{UnitOfTime.SECONDS}",
    MeasuredValueType.LENGTH_IN_METER: UnitOfLength.METERS,
    MeasuredValueType.LINEAR_SPEED_IN_METER_PER_SECOND: UnitOfSpeed.METERS_PER_SECOND,
    MeasuredValueType.LUMINANCE_IN_LUX: LIGHT_LUX,
    MeasuredValueType.PARTS_PER_BILLION: CONCENTRATION_PARTS_PER_BILLION,
    MeasuredValueType.PARTS_PER_MILLION: CONCENTRATION_PARTS_PER_MILLION,
    MeasuredValueType.PARTS_PER_QUADRILLION: "ppq",
    MeasuredValueType.PARTS_PER_TRILLION: "ppt",
    MeasuredValueType.POWER_PER_SQUARE_METER: UnitOfIrradiance.WATTS_PER_SQUARE_METER,
    MeasuredValueType.PRESSURE_IN_HPA: UnitOfPressure.HPA,
    MeasuredValueType.PRESSURE_IN_MILLI_BAR: UnitOfPressure.MBAR,
    MeasuredValueType.RELATIVE_VALUE_IN_PERCENTAGE: PERCENTAGE,
    MeasuredValueType.TEMPERATURE_IN_CELCIUS: UnitOfTemperature.CELSIUS,
    MeasuredValueType.TEMPERATURE_IN_KELVIN: UnitOfTemperature.KELVIN,
    MeasuredValueType.TIME_IN_SECOND: UnitOfTime.SECONDS,
    # MeasuredValueType.VECTOR_COORDINATE: "",
    MeasuredValueType.VOLTAGE_IN_MILLI_VOLT: UnitOfElectricPotential.MILLIVOLT,
    MeasuredValueType.VOLTAGE_IN_VOLT: UnitOfElectricPotential.VOLT,
    MeasuredValueType.VOLUME_IN_CUBIC_METER: UnitOfVolume.CUBIC_METERS,
    MeasuredValueType.VOLUME_IN_GALLON: UnitOfVolume.GALLONS,
    MeasuredValueType.VOLUME_IN_LITER: UnitOfVolume.LITERS,
}
