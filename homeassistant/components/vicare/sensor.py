"""Viessmann ViCare sensor device."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceWithComponent,
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

from . import ViCareRequiredKeysMixin
from .const import (
    DOMAIN,
    VICARE_API,
    VICARE_CUBIC_METER,
    VICARE_DEVICE_CONFIG,
    VICARE_KWH,
    VICARE_UNIT_TO_UNIT_OF_MEASUREMENT,
)
from .entity import ViCareEntity
from .utils import get_burners, get_circuits, get_compressors, is_supported

_LOGGER = logging.getLogger(__name__)

VICARE_UNIT_TO_DEVICE_CLASS = {
    VICARE_KWH: SensorDeviceClass.ENERGY,
    VICARE_CUBIC_METER: SensorDeviceClass.GAS,
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
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        value_getter=lambda api: api.getVolumetricFlowReturn() / 1000,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
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
        icon="mdi:counter",
        value_getter=lambda api: api.getStarts(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="burner_hours",
        translation_key="burner_hours",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHours(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="burner_modulation",
        translation_key="burner_modulation",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        value_getter=lambda api: api.getModulation(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

COMPRESSOR_SENSORS: tuple[ViCareSensorEntityDescription, ...] = (
    ViCareSensorEntityDescription(
        key="compressor_starts",
        translation_key="compressor_starts",
        icon="mdi:counter",
        value_getter=lambda api: api.getStarts(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours",
        translation_key="compressor_hours",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHours(),
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass1",
        translation_key="compressor_hours_loadclass1",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass1(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass2",
        translation_key="compressor_hours_loadclass2",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass2(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass3",
        translation_key="compressor_hours_loadclass3",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass3(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass4",
        translation_key="compressor_hours_loadclass4",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass4(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_hours_loadclass5",
        translation_key="compressor_hours_loadclass5",
        icon="mdi:counter",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_getter=lambda api: api.getHoursLoadClass5(),
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ViCareSensorEntityDescription(
        key="compressor_phase",
        translation_key="compressor_phase",
        icon="mdi:information",
        value_getter=lambda api: api.getPhase(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _build_entities(
    device: PyViCareDevice,
    device_config: PyViCareDeviceConfig,
) -> list[ViCareSensor]:
    """Create ViCare sensor entities for a device."""

    entities: list[ViCareSensor] = _build_entities_for_device(device, device_config)
    entities.extend(
        _build_entities_for_component(
            get_circuits(device), device_config, CIRCUIT_SENSORS
        )
    )
    entities.extend(
        _build_entities_for_component(
            get_burners(device), device_config, BURNER_SENSORS
        )
    )
    entities.extend(
        _build_entities_for_component(
            get_compressors(device), device_config, COMPRESSOR_SENSORS
        )
    )
    return entities


def _build_entities_for_device(
    device: PyViCareDevice,
    device_config: PyViCareDeviceConfig,
) -> list[ViCareSensor]:
    """Create device specific ViCare sensor entities."""

    return [
        ViCareSensor(
            device,
            device_config,
            description,
        )
        for description in GLOBAL_SENSORS
        if is_supported(description.key, description, device)
    ]


def _build_entities_for_component(
    components: list[PyViCareHeatingDeviceWithComponent],
    device_config: PyViCareDeviceConfig,
    entity_descriptions: tuple[ViCareSensorEntityDescription, ...],
) -> list[ViCareSensor]:
    """Create component specific ViCare sensor entities."""

    return [
        ViCareSensor(
            component,
            device_config,
            description,
        )
        for component in components
        for description in entity_descriptions
        if is_supported(description.key, description, component)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the ViCare sensor devices."""
    api: PyViCareDevice = hass.data[DOMAIN][config_entry.entry_id][VICARE_API]
    device_config: PyViCareDeviceConfig = hass.data[DOMAIN][config_entry.entry_id][
        VICARE_DEVICE_CONFIG
    ]

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            api,
            device_config,
        )
    )


class ViCareSensor(ViCareEntity, SensorEntity):
    """Representation of a ViCare sensor."""

    entity_description: ViCareSensorEntityDescription

    def __init__(
        self,
        api,
        device_config: PyViCareDeviceConfig,
        description: ViCareSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device_config, api, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    def update(self) -> None:
        """Update state of sensor."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_native_value = self.entity_description.value_getter(
                    self._api
                )

                if self.entity_description.unit_getter:
                    vicare_unit = self.entity_description.unit_getter(self._api)
                    if vicare_unit is not None:
                        self._attr_device_class = VICARE_UNIT_TO_DEVICE_CLASS.get(
                            vicare_unit
                        )
                        self._attr_native_unit_of_measurement = (
                            VICARE_UNIT_TO_UNIT_OF_MEASUREMENT.get(vicare_unit)
                        )
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)
