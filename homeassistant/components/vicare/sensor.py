"""Viessmann ViCare sensor device."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_LIST,
    DOMAIN,
    VICARE_CUBIC_METER,
    VICARE_KW,
    VICARE_KWH,
    VICARE_PERCENT,
    VICARE_W,
    VICARE_WH,
)
from .entity import ViCareEntity
from .types import ViCareDevice, ViCareRequiredKeysMixin
from .utils import get_burners, get_circuits, get_compressors, is_supported

_LOGGER = logging.getLogger(__name__)

VICARE_UNIT_TO_DEVICE_CLASS = {
    VICARE_WH: SensorDeviceClass.ENERGY,
    VICARE_KWH: SensorDeviceClass.ENERGY,
    VICARE_W: SensorDeviceClass.POWER,
    VICARE_KW: SensorDeviceClass.POWER,
    VICARE_CUBIC_METER: SensorDeviceClass.GAS,
}

VICARE_UNIT_TO_HA_UNIT = {
    VICARE_PERCENT: PERCENTAGE,
    VICARE_W: UnitOfPower.WATT,
    VICARE_KW: UnitOfPower.KILO_WATT,
    VICARE_WH: UnitOfEnergy.WATT_HOUR,
    VICARE_KWH: UnitOfEnergy.KILO_WATT_HOUR,
    VICARE_CUBIC_METER: UnitOfVolume.CUBIC_METERS,
}


@dataclass(frozen=True)
class ViCareSensorEntityDescription(SensorEntityDescription, ViCareRequiredKeysMixin):
    """Describes ViCare sensor entity."""

    unit_getter: Callable[[PyViCareDevice], str | None] | None = None


GLOBAL_SENSORS: tuple[ViCareSensorEntityDescription, ...] = (
    ViCareSensorEntityDescription(
        key="outside_temperature",
        translation_key="outside_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getOutsideTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="return_temperature",
        translation_key="return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getReturnTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="boiler_temperature",
        translation_key="boiler_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getBoilerTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="boiler_supply_temperature",
        translation_key="boiler_supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getBoilerCommonSupplyTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="primary_circuit_supply_temperature",
        translation_key="primary_circuit_supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getSupplyTemperaturePrimaryCircuit(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="primary_circuit_return_temperature",
        translation_key="primary_circuit_return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getReturnTemperaturePrimaryCircuit(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="secondary_circuit_supply_temperature",
        translation_key="secondary_circuit_supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getSupplyTemperatureSecondaryCircuit(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="secondary_circuit_return_temperature",
        translation_key="secondary_circuit_return_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getReturnTemperatureSecondaryCircuit(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_out_temperature",
        translation_key="hotwater_out_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDomesticHotWaterOutletTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_max_temperature",
        translation_key="hotwater_max_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDomesticHotWaterMaxTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_min_temperature",
        translation_key="hotwater_min_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getDomesticHotWaterMinTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_consumption_today",
        translation_key="hotwater_gas_consumption_today",
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterToday(),
        unit_getter=lambda api: api.getGasConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_consumption_heating_this_week",
        translation_key="hotwater_gas_consumption_heating_this_week",
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterThisWeek(),
        unit_getter=lambda api: api.getGasConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_consumption_heating_this_month",
        translation_key="hotwater_gas_consumption_heating_this_month",
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterThisMonth(),
        unit_getter=lambda api: api.getGasConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_consumption_heating_this_year",
        translation_key="hotwater_gas_consumption_heating_this_year",
        value_getter=lambda api: api.getGasConsumptionDomesticHotWaterThisYear(),
        unit_getter=lambda api: api.getGasConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_heating_today",
        translation_key="gas_consumption_heating_today",
        value_getter=lambda api: api.getGasConsumptionHeatingToday(),
        unit_getter=lambda api: api.getGasConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_heating_this_week",
        translation_key="gas_consumption_heating_this_week",
        value_getter=lambda api: api.getGasConsumptionHeatingThisWeek(),
        unit_getter=lambda api: api.getGasConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_heating_this_month",
        translation_key="gas_consumption_heating_this_month",
        value_getter=lambda api: api.getGasConsumptionHeatingThisMonth(),
        unit_getter=lambda api: api.getGasConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_heating_this_year",
        translation_key="gas_consumption_heating_this_year",
        value_getter=lambda api: api.getGasConsumptionHeatingThisYear(),
        unit_getter=lambda api: api.getGasConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_fuelcell_today",
        translation_key="gas_consumption_fuelcell_today",
        value_getter=lambda api: api.getFuelCellGasConsumptionToday(),
        unit_getter=lambda api: api.getFuelCellGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_fuelcell_this_week",
        translation_key="gas_consumption_fuelcell_this_week",
        value_getter=lambda api: api.getFuelCellGasConsumptionThisWeek(),
        unit_getter=lambda api: api.getFuelCellGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_fuelcell_this_month",
        translation_key="gas_consumption_fuelcell_this_month",
        value_getter=lambda api: api.getFuelCellGasConsumptionThisMonth(),
        unit_getter=lambda api: api.getFuelCellGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_fuelcell_this_year",
        translation_key="gas_consumption_fuelcell_this_year",
        value_getter=lambda api: api.getFuelCellGasConsumptionThisYear(),
        unit_getter=lambda api: api.getFuelCellGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_total_today",
        translation_key="gas_consumption_total_today",
        value_getter=lambda api: api.getGasConsumptionTotalToday(),
        unit_getter=lambda api: api.getGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_total_this_week",
        translation_key="gas_consumption_total_this_week",
        value_getter=lambda api: api.getGasConsumptionTotalThisWeek(),
        unit_getter=lambda api: api.getGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_total_this_month",
        translation_key="gas_consumption_total_this_month",
        value_getter=lambda api: api.getGasConsumptionTotalThisMonth(),
        unit_getter=lambda api: api.getGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_consumption_total_this_year",
        translation_key="gas_consumption_total_this_year",
        value_getter=lambda api: api.getGasConsumptionTotalThisYear(),
        unit_getter=lambda api: api.getGasConsumptionUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_summary_consumption_heating_currentday",
        translation_key="gas_summary_consumption_heating_currentday",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionHeatingCurrentDay(),
        unit_getter=lambda api: api.getGasSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="gas_summary_consumption_heating_currentmonth",
        translation_key="gas_summary_consumption_heating_currentmonth",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionHeatingCurrentMonth(),
        unit_getter=lambda api: api.getGasSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_summary_consumption_heating_currentyear",
        translation_key="gas_summary_consumption_heating_currentyear",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionHeatingCurrentYear(),
        unit_getter=lambda api: api.getGasSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="gas_summary_consumption_heating_lastsevendays",
        translation_key="gas_summary_consumption_heating_lastsevendays",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionHeatingLastSevenDays(),
        unit_getter=lambda api: api.getGasSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_summary_consumption_heating_currentday",
        translation_key="hotwater_gas_summary_consumption_heating_currentday",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterCurrentDay(),
        unit_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_summary_consumption_heating_currentmonth",
        translation_key="hotwater_gas_summary_consumption_heating_currentmonth",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterCurrentMonth(),
        unit_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_summary_consumption_heating_currentyear",
        translation_key="hotwater_gas_summary_consumption_heating_currentyear",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterCurrentYear(),
        unit_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="hotwater_gas_summary_consumption_heating_lastsevendays",
        translation_key="hotwater_gas_summary_consumption_heating_lastsevendays",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterLastSevenDays(),
        unit_getter=lambda api: api.getGasSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="energy_summary_consumption_heating_currentday",
        translation_key="energy_summary_consumption_heating_currentday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionHeatingCurrentDay(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="energy_summary_consumption_heating_currentmonth",
        translation_key="energy_summary_consumption_heating_currentmonth",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionHeatingCurrentMonth(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="energy_summary_consumption_heating_currentyear",
        translation_key="energy_summary_consumption_heating_currentyear",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionHeatingCurrentYear(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="energy_summary_consumption_heating_lastsevendays",
        translation_key="energy_summary_consumption_heating_lastsevendays",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionHeatingLastSevenDays(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionHeatingUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="energy_dhw_summary_consumption_heating_currentday",
        translation_key="energy_dhw_summary_consumption_heating_currentday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterCurrentDay(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="energy_dhw_summary_consumption_heating_currentmonth",
        translation_key="energy_dhw_summary_consumption_heating_currentmonth",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterCurrentMonth(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="energy_dhw_summary_consumption_heating_currentyear",
        translation_key="energy_dhw_summary_consumption_heating_currentyear",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterCurrentYear(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="energy_summary_dhw_consumption_heating_lastsevendays",
        translation_key="energy_summary_dhw_consumption_heating_lastsevendays",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterLastSevenDays(),
        unit_getter=lambda api: api.getPowerSummaryConsumptionDomesticHotWaterUnit(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="power_production_current",
        translation_key="power_production_current",
        native_unit_of_measurement=UnitOfPower.WATT,
        value_getter=lambda api: api.getPowerProductionCurrent(),
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="power_production_today",
        translation_key="power_production_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionToday(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="power_production_this_week",
        translation_key="power_production_this_week",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionThisWeek(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="power_production_this_month",
        translation_key="power_production_this_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionThisMonth(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="power_production_this_year",
        translation_key="power_production_this_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerProductionThisYear(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="solar storage temperature",
        translation_key="solar_storage_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getSolarStorageTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="collector temperature",
        translation_key="collector_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getSolarCollectorTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="solar power production today",
        translation_key="solar_power_production_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getSolarPowerProductionToday(),
        unit_getter=lambda api: api.getSolarPowerProductionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="solar power production this week",
        translation_key="solar_power_production_this_week",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getSolarPowerProductionThisWeek(),
        unit_getter=lambda api: api.getSolarPowerProductionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="solar power production this month",
        translation_key="solar_power_production_this_month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getSolarPowerProductionThisMonth(),
        unit_getter=lambda api: api.getSolarPowerProductionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="solar power production this year",
        translation_key="solar_power_production_this_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getSolarPowerProductionThisYear(),
        unit_getter=lambda api: api.getSolarPowerProductionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="power consumption today",
        translation_key="power_consumption_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerConsumptionToday(),
        unit_getter=lambda api: api.getPowerConsumptionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="power consumption this week",
        translation_key="power_consumption_this_week",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerConsumptionThisWeek(),
        unit_getter=lambda api: api.getPowerConsumptionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="power consumption this month",
        translation_key="power consumption this month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerConsumptionThisMonth(),
        unit_getter=lambda api: api.getPowerConsumptionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="power consumption this year",
        translation_key="power_consumption_this_year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_getter=lambda api: api.getPowerConsumptionThisYear(),
        unit_getter=lambda api: api.getPowerConsumptionUnit(),
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="buffer top temperature",
        translation_key="buffer_top_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getBufferTopTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="buffer main temperature",
        translation_key="buffer_main_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getBufferMainTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="volumetric_flow",
        translation_key="volumetric_flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        value_getter=lambda api: api.getVolumetricFlowReturn() / 1000,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ViCareSensorEntityDescription(
        key="ess_state_of_charge",
        translation_key="ess_state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_getter=lambda api: api.getElectricalEnergySystemSOC(),
        unit_getter=lambda api: api.getElectricalEnergySystemSOCUnit(),
    ),
    ViCareSensorEntityDescription(
        key="ess_power_current",
        translation_key="ess_power_current",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_getter=lambda api: api.getElectricalEnergySystemPower(),
        unit_getter=lambda api: api.getElectricalEnergySystemPowerUnit(),
    ),
    ViCareSensorEntityDescription(
        key="ess_state",
        translation_key="ess_state",
        device_class=SensorDeviceClass.ENUM,
        options=["charge", "discharge", "standby"],
        value_getter=lambda api: api.getElectricalEnergySystemOperationState(),
    ),
    ViCareSensorEntityDescription(
        key="ess_discharge_today",
        translation_key="ess_discharge_today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedCurrentDay(),
        unit_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedUnit(),
    ),
    ViCareSensorEntityDescription(
        key="ess_discharge_this_week",
        translation_key="ess_discharge_this_week",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedCurrentWeek(),
        unit_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="ess_discharge_this_month",
        translation_key="ess_discharge_this_month",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedCurrentMonth(),
        unit_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="ess_discharge_this_year",
        translation_key="ess_discharge_this_year",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedCurrentYear(),
        unit_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="ess_discharge_total",
        translation_key="ess_discharge_total",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedLifeCycle(),
        unit_getter=lambda api: api.getElectricalEnergySystemTransferDischargeCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="pcc_transfer_power_exchange",
        translation_key="pcc_transfer_power_exchange",
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_getter=lambda api: api.getPointOfCommonCouplingTransferPowerExchange(),
    ),
    ViCareSensorEntityDescription(
        key="pcc_energy_consumption",
        translation_key="pcc_energy_consumption",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPointOfCommonCouplingTransferConsumptionTotal(),
        unit_getter=lambda api: api.getPointOfCommonCouplingTransferConsumptionTotalUnit(),
    ),
    ViCareSensorEntityDescription(
        key="pcc_energy_feed_in",
        translation_key="pcc_energy_feed_in",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPointOfCommonCouplingTransferFeedInTotal(),
        unit_getter=lambda api: api.getPointOfCommonCouplingTransferFeedInTotalUnit(),
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_power_production_current",
        translation_key="photovoltaic_power_production_current",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_getter=lambda api: api.getPhotovoltaicProductionCurrent(),
        unit_getter=lambda api: api.getPhotovoltaicProductionCurrentUnit(),
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_energy_production_today",
        translation_key="photovoltaic_energy_production_today",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPhotovoltaicProductionCumulatedCurrentDay(),
        unit_getter=lambda api: api.getPhotovoltaicProductionCumulatedUnit(),
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_energy_production_this_week",
        translation_key="photovoltaic_energy_production_this_week",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPhotovoltaicProductionCumulatedCurrentWeek(),
        unit_getter=lambda api: api.getPhotovoltaicProductionCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_energy_production_this_month",
        translation_key="photovoltaic_energy_production_this_month",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPhotovoltaicProductionCumulatedCurrentMonth(),
        unit_getter=lambda api: api.getPhotovoltaicProductionCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_energy_production_this_year",
        translation_key="photovoltaic_energy_production_this_year",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPhotovoltaicProductionCumulatedCurrentYear(),
        unit_getter=lambda api: api.getPhotovoltaicProductionCumulatedUnit(),
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_energy_production_total",
        translation_key="photovoltaic_energy_production_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_getter=lambda api: api.getPhotovoltaicProductionCumulatedLifeCycle(),
        unit_getter=lambda api: api.getPhotovoltaicProductionCumulatedUnit(),
    ),
    ViCareSensorEntityDescription(
        key="photovoltaic_status",
        translation_key="photovoltaic_status",
        device_class=SensorDeviceClass.ENUM,
        options=["ready", "production"],
        value_getter=lambda api: _filter_pv_states(api.getPhotovoltaicStatus()),
    ),
)

CIRCUIT_SENSORS: tuple[ViCareSensorEntityDescription, ...] = (
    ViCareSensorEntityDescription(
        key="supply_temperature",
        translation_key="supply_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_getter=lambda api: api.getSupplyTemperature(),
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

BURNER_SENSORS: tuple[ViCareSensorEntityDescription, ...] = (
    ViCareSensorEntityDescription(
        key="burner_starts",
        translation_key="burner_starts",
        value_getter=lambda api: api.getStarts(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="burner_hours",
        translation_key="burner_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHours(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="burner_modulation",
        translation_key="burner_modulation",
        native_unit_of_measurement=PERCENTAGE,
        value_getter=lambda api: api.getModulation(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareSensorEntityDescription, ...] = (
    ViCareSensorEntityDescription(
        key="compressor_starts",
        translation_key="compressor_starts",
        value_getter=lambda api: api.getStarts(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours",
        translation_key="compressor_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHours(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass1",
        translation_key="compressor_hours_loadclass1",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass1(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass2",
        translation_key="compressor_hours_loadclass2",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass2(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass3",
        translation_key="compressor_hours_loadclass3",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass3(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass4",
        translation_key="compressor_hours_loadclass4",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass4(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass5",
        translation_key="compressor_hours_loadclass5",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass5(),
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_phase",
        translation_key="compressor_phase",
        value_getter=lambda api: api.getPhase(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _filter_pv_states(state: str) -> str | None:
    return None if state in ("nothing", "unknown") else state


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareSensor]:
    """Create ViCare sensor entities for a device."""

    entities: list[ViCareSensor] = []
    for device in device_list:
        # add device entities
        entities.extend(
            ViCareSensor(
                description,
                device.config,
                device.api,
            )
            for description in GLOBAL_SENSORS
            if is_supported(description.key, description, device.api)
        )
        # add component entities
        for component_list, entity_description_list in (
            (get_circuits(device.api), CIRCUIT_SENSORS),
            (get_burners(device.api), BURNER_SENSORS),
            (get_compressors(device.api), COMPRESSOR_SENSORS),
        ):
            entities.extend(
                ViCareSensor(
                    description,
                    device.config,
                    device.api,
                    component,
                )
                for component in component_list
                for description in entity_description_list
                if is_supported(description.key, description, component)
            )
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare sensor devices."""
    device_list = hass.data[DOMAIN][config_entry.entry_id][DEVICE_LIST]

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            device_list,
        ),
        # run update to have device_class set depending on unit_of_measurement
        True,
    )


class ViCareSensor(ViCareEntity, SensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareSensorEntityDescription

    def __init__(
        self,
        description: ViCareSensorEntityDescription,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(description.key, device_config, device, component)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    def update(self) -> None:
        """Update state of sensor."""
        vicare_unit = None
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_value = self.entity_description.value_getter(
                    self._api
                )

                if self.entity_description.unit_getter:
                    vicare_unit = self.entity_description.unit_getter(self._api)
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

        if vicare_unit is not None:
            if (
                device_class := VICARE_UNIT_TO_DEVICE_CLASS.get(vicare_unit)
            ) is not None:
                self._attr_device_class = device_class
            self._attr_native_unit_of_measurement = VICARE_UNIT_TO_HA_UNIT.get(
                vicare_unit
            )
