"""Constants for the Wibeee integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
)

DOMAIN = "wibeee"

DEFAULT_TIMEOUT = timedelta(seconds=10)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_HA_PORT = 8123

CONF_MAC_ADDRESS = "mac_address"
CONF_WIBEEE_ID = "wibeee_id"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_UPDATE_MODE = "update_mode"
CONF_AUTO_CONFIGURE = "auto_configure"

MODE_POLLING = "polling"
MODE_LOCAL_PUSH = "local_push"

KNOWN_MODELS = {
    "WBM": "Wibeee 1Ph",
    "WBT": "Wibeee 3Ph",
    "WMX": "Wibeee MAX",
    "WTD": "Wibeee 3Ph RN",
    "WX2": "Wibeee MAX 2S",
    "WX3": "Wibeee MAX 3S",
    "WXX": "Wibeee MAX MS",
    "WBB": "Wibeee BOX",
    "WB3": "Wibeee BOX S3P",
    "W3P": "Wibeee 3Ph 3W",
    "WGD": "Wibeee GND",
    "WBP": "Wibeee SMART PLUG",
}

PUSH_PARAM_TO_SENSOR: dict[str, str] = {
    "v": "vrms",
    "i": "irms",
    "p": "p_aparent",
    "a": "p_activa",
    "r": "p_reactiva_ind",
    "q": "frecuencia",
    "f": "factor_potencia",
    "e": "energia_activa",
    "o": "energia_reactiva_ind",
}

PUSH_PHASE_MAP: dict[str, str] = {
    "1": "fase1",
    "2": "fase2",
    "3": "fase3",
    "t": "fase4",
}


SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "vrms": SensorEntityDescription(
        key="vrms",
        translation_key="phase_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "irms": SensorEntityDescription(
        key="irms",
        translation_key="current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_aparent": SensorEntityDescription(
        key="p_aparent",
        translation_key="apparent_power",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_activa": SensorEntityDescription(
        key="p_activa",
        translation_key="active_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_reactiva_ind": SensorEntityDescription(
        key="p_reactiva_ind",
        translation_key="inductive_reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "p_reactiva_cap": SensorEntityDescription(
        key="p_reactiva_cap",
        translation_key="capacitive_reactive_power",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "frecuencia": SensorEntityDescription(
        key="frecuencia",
        translation_key="frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "factor_potencia": SensorEntityDescription(
        key="factor_potencia",
        translation_key="power_factor",
        native_unit_of_measurement=None,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "energia_activa": SensorEntityDescription(
        key="energia_activa",
        translation_key="active_energy",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_reactiva_ind": SensorEntityDescription(
        key="energia_reactiva_ind",
        translation_key="inductive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        device_class=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "energia_reactiva_cap": SensorEntityDescription(
        key="energia_reactiva_cap",
        translation_key="capacitive_reactive_energy",
        native_unit_of_measurement=UnitOfReactiveEnergy.VOLT_AMPERE_REACTIVE_HOUR,
        device_class=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    "angle": SensorEntityDescription(
        key="angle",
        translation_key="angle",
        native_unit_of_measurement=DEGREE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_total": SensorEntityDescription(
        key="thd_total",
        translation_key="thd_current",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_fund": SensorEntityDescription(
        key="thd_fund",
        translation_key="thd_current_fundamental",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar3": SensorEntityDescription(
        key="thd_ar3",
        translation_key="thd_current_harmonic_3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar5": SensorEntityDescription(
        key="thd_ar5",
        translation_key="thd_current_harmonic_5",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar7": SensorEntityDescription(
        key="thd_ar7",
        translation_key="thd_current_harmonic_7",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar9": SensorEntityDescription(
        key="thd_ar9",
        translation_key="thd_current_harmonic_9",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_tot_V": SensorEntityDescription(
        key="thd_tot_V",
        translation_key="thd_voltage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_fun_V": SensorEntityDescription(
        key="thd_fun_V",
        translation_key="thd_voltage_fundamental",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar3_V": SensorEntityDescription(
        key="thd_ar3_V",
        translation_key="thd_voltage_harmonic_3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar5_V": SensorEntityDescription(
        key="thd_ar5_V",
        translation_key="thd_voltage_harmonic_5",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar7_V": SensorEntityDescription(
        key="thd_ar7_V",
        translation_key="thd_voltage_harmonic_7",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "thd_ar9_V": SensorEntityDescription(
        key="thd_ar9_V",
        translation_key="thd_voltage_harmonic_9",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}
