"""Support for Dutch Smart Meter (also known as Smartmeter or P1 port)."""

import asyncio
from asyncio import CancelledError
from collections.abc import Callable, Generator
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import IntEnum
from functools import partial
from typing import Any, override
from urllib.parse import urlparse

from dsmr_parser.clients.protocol import create_dsmr_reader
from dsmr_parser.clients.rfxtrx_protocol import (
    create_rfxtrx_dsmr_reader,
    create_rfxtrx_tcp_dsmr_reader,
)
from dsmr_parser.objects import DSMRObject, MbusDevice, Telegram

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
    EntityCategory,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType

from . import DsmrConfigEntry
from .const import (
    CONF_DSMR_VERSION,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    CONF_TIME_BETWEEN_UPDATE,
    DEFAULT_PRECISION,
    DEFAULT_RECONNECT_INTERVAL,
    DEFAULT_TIME_BETWEEN_UPDATE,
    DEVICE_NAME_ELECTRICITY,
    DEVICE_NAME_GAS,
    DEVICE_NAME_HEAT,
    DEVICE_NAME_WATER,
    DOMAIN,
    DSMR_PROTOCOL,
    LOGGER,
    RFXTRX_DSMR_PROTOCOL,
)

EVENT_FIRST_TELEGRAM = "dsmr_first_telegram_{}"

UNIT_CONVERSION = {"m3": UnitOfVolume.CUBIC_METERS}


@dataclass(frozen=True, kw_only=True)
class DSMRSensorEntityDescription(SensorEntityDescription):
    """Represents an DSMR Sensor."""

    dsmr_versions: set[str] | None = None
    is_gas: bool = False
    is_water: bool = False
    is_heat: bool = False
    average: bool = False
    obis_reference: str


class MbusDeviceType(IntEnum):
    """Types of mbus devices (13757-3:2013)."""

    GAS = 3
    HEAT = 4
    WATER = 7
    HEAT_COOL = 12


SENSORS: tuple[DSMRSensorEntityDescription, ...] = (
    DSMRSensorEntityDescription(
        key="timestamp",
        obis_reference="P1_MESSAGE_TIMESTAMP",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    DSMRSensorEntityDescription(
        key="current_electricity_usage",
        average=True,
        translation_key="current_electricity_usage",
        obis_reference="CURRENT_ELECTRICITY_USAGE",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="current_electricity_delivery",
        average=True,
        translation_key="current_electricity_delivery",
        obis_reference="CURRENT_ELECTRICITY_DELIVERY",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="electricity_active_tariff",
        translation_key="electricity_active_tariff",
        obis_reference="ELECTRICITY_ACTIVE_TARIFF",
        dsmr_versions={"2.2", "4", "5", "5B", "5L", "5EONHU"},
        device_class=SensorDeviceClass.ENUM,
        options=["low", "normal"],
    ),
    DSMRSensorEntityDescription(
        key="electricity_used_tariff_1",
        translation_key="electricity_used_tariff_1",
        obis_reference="ELECTRICITY_USED_TARIFF_1",
        dsmr_versions={"2.2", "4", "5", "5B", "5L", "5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_used_tariff_2",
        translation_key="electricity_used_tariff_2",
        obis_reference="ELECTRICITY_USED_TARIFF_2",
        dsmr_versions={"2.2", "4", "5", "5B", "5L", "5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_used_tariff_3",
        translation_key="electricity_used_tariff_3",
        obis_reference="ELECTRICITY_USED_TARIFF_3",
        dsmr_versions={"5EONHU"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_used_tariff_4",
        translation_key="electricity_used_tariff_4",
        obis_reference="ELECTRICITY_USED_TARIFF_4",
        dsmr_versions={"5EONHU"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_delivered_tariff_1",
        translation_key="electricity_delivered_tariff_1",
        obis_reference="ELECTRICITY_DELIVERED_TARIFF_1",
        dsmr_versions={"2.2", "4", "5", "5B", "5L", "5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_delivered_tariff_2",
        translation_key="electricity_delivered_tariff_2",
        obis_reference="ELECTRICITY_DELIVERED_TARIFF_2",
        dsmr_versions={"2.2", "4", "5", "5B", "5L", "5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_delivered_tariff_3",
        translation_key="electricity_delivered_tariff_3",
        obis_reference="ELECTRICITY_DELIVERED_TARIFF_3",
        dsmr_versions={"5EONHU"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_delivered_tariff_4",
        translation_key="electricity_delivered_tariff_4",
        obis_reference="ELECTRICITY_DELIVERED_TARIFF_4",
        dsmr_versions={"5EONHU"},
        force_update=True,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l1_positive",
        average=True,
        translation_key="instantaneous_active_power_l1_positive",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l2_positive",
        average=True,
        translation_key="instantaneous_active_power_l2_positive",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l3_positive",
        average=True,
        translation_key="instantaneous_active_power_l3_positive",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l1_negative",
        average=True,
        translation_key="instantaneous_active_power_l1_negative",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l2_negative",
        average=True,
        translation_key="instantaneous_active_power_l2_negative",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_active_power_l3_negative",
        average=True,
        translation_key="instantaneous_active_power_l3_negative",
        obis_reference="INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE",
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="short_power_failure_count",
        translation_key="short_power_failure_count",
        obis_reference="SHORT_POWER_FAILURE_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="long_power_failure_count",
        translation_key="long_power_failure_count",
        obis_reference="LONG_POWER_FAILURE_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_sag_l1_count",
        translation_key="voltage_sag_l1_count",
        obis_reference="VOLTAGE_SAG_L1_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_sag_l2_count",
        translation_key="voltage_sag_l2_count",
        obis_reference="VOLTAGE_SAG_L2_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_sag_l3_count",
        translation_key="voltage_sag_l3_count",
        obis_reference="VOLTAGE_SAG_L3_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_swell_l1_count",
        translation_key="voltage_swell_l1_count",
        obis_reference="VOLTAGE_SWELL_L1_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_swell_l2_count",
        translation_key="voltage_swell_l2_count",
        obis_reference="VOLTAGE_SWELL_L2_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="voltage_swell_l3_count",
        translation_key="voltage_swell_l3_count",
        obis_reference="VOLTAGE_SWELL_L3_COUNT",
        dsmr_versions={"2.2", "4", "5", "5L"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_voltage_l1",
        average=True,
        translation_key="instantaneous_voltage_l1",
        obis_reference="INSTANTANEOUS_VOLTAGE_L1",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_voltage_l2",
        average=True,
        translation_key="instantaneous_voltage_l2",
        obis_reference="INSTANTANEOUS_VOLTAGE_L2",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_voltage_l3",
        average=True,
        translation_key="instantaneous_voltage_l3",
        obis_reference="INSTANTANEOUS_VOLTAGE_L3",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_current_l1",
        average=True,
        translation_key="instantaneous_current_l1",
        obis_reference="INSTANTANEOUS_CURRENT_L1",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_current_l2",
        average=True,
        translation_key="instantaneous_current_l2",
        obis_reference="INSTANTANEOUS_CURRENT_L2",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="instantaneous_current_l3",
        average=True,
        translation_key="instantaneous_current_l3",
        obis_reference="INSTANTANEOUS_CURRENT_L3",
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="belgium_max_power_per_phase",
        translation_key="max_power_per_phase",
        obis_reference="ACTUAL_TRESHOLD_ELECTRICITY",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="belgium_max_current_per_phase",
        translation_key="max_current_per_phase",
        obis_reference="FUSE_THRESHOLD_L1",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="electricity_imported_total",
        translation_key="electricity_imported_total",
        obis_reference="ELECTRICITY_IMPORTED_TOTAL",
        dsmr_versions={"5L", "5S", "Q3D", "5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="electricity_exported_total",
        translation_key="electricity_exported_total",
        obis_reference="ELECTRICITY_EXPORTED_TOTAL",
        dsmr_versions={"5L", "5S", "Q3D", "5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="belgium_current_average_demand",
        translation_key="current_average_demand",
        obis_reference="BELGIUM_CURRENT_AVERAGE_DEMAND",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="belgium_maximum_demand_current_month",
        translation_key="maximum_demand_current_month",
        obis_reference="BELGIUM_MAXIMUM_DEMAND_MONTH",
        dsmr_versions={"5B"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DSMRSensorEntityDescription(
        key="hourly_gas_meter_reading",
        translation_key="gas_meter_reading",
        obis_reference="HOURLY_GAS_METER_READING",
        dsmr_versions={"4", "5", "5L"},
        is_gas=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="gas_meter_reading",
        translation_key="gas_meter_reading",
        obis_reference="GAS_METER_READING",
        dsmr_versions={"2.2"},
        is_gas=True,
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    DSMRSensorEntityDescription(
        key="actual_threshold_electricity",
        translation_key="actual_threshold_electricity",
        obis_reference="ACTUAL_TRESHOLD_ELECTRICITY",  # Misspelled in external tool
        dsmr_versions={"5EONHU"},
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="eon_hu_electricity_combined",
        translation_key="electricity_combined",
        obis_reference="EON_HU_ELECTRICITY_COMBINED",
        dsmr_versions={"5EONHU"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    DSMRSensorEntityDescription(
        key="eon_hu_instantaneous_power_factor_total",
        average=True,
        translation_key="instantaneous_power_factor_total",
        obis_reference="EON_HU_INSTANTANEOUS_POWER_FACTOR_TOTAL",
        dsmr_versions={"5EONHU"},
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="eon_hu_instantaneous_power_factor_l1",
        average=True,
        translation_key="instantaneous_power_factor_l1",
        obis_reference="EON_HU_INSTANTANEOUS_POWER_FACTOR_L1",
        dsmr_versions={"5EONHU"},
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="eon_hu_instantaneous_power_factor_l2",
        average=True,
        translation_key="instantaneous_power_factor_l2",
        obis_reference="EON_HU_INSTANTANEOUS_POWER_FACTOR_L2",
        dsmr_versions={"5EONHU"},
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="eon_hu_instantaneous_power_factor_l3",
        average=True,
        translation_key="instantaneous_power_factor_l3",
        obis_reference="EON_HU_INSTANTANEOUS_POWER_FACTOR_L3",
        dsmr_versions={"5EONHU"},
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="eon_hu_frequency",
        average=True,
        translation_key="frequency",
        obis_reference="EON_HU_FREQUENCY",
        dsmr_versions={"5EONHU"},
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="fuse_threshold_l1",
        translation_key="fuse_threshold_l1",
        obis_reference="FUSE_THRESHOLD_L1",
        dsmr_versions={"5EONHU"},
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="fuse_threshold_l2",
        translation_key="fuse_threshold_l2",
        obis_reference="FUSE_THRESHOLD_L2",
        dsmr_versions={"5EONHU"},
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="fuse_threshold_l3",
        translation_key="fuse_threshold_l3",
        obis_reference="FUSE_THRESHOLD_L3",
        dsmr_versions={"5EONHU"},
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DSMRSensorEntityDescription(
        key="text_message",
        translation_key="text_message",
        obis_reference="TEXT_MESSAGE",
        dsmr_versions={"5EONHU"},
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

SENSORS_MBUS_DEVICE_TYPE: dict[int, tuple[DSMRSensorEntityDescription, ...]] = {
    MbusDeviceType.GAS: (
        DSMRSensorEntityDescription(
            key="gas_reading",
            translation_key="gas_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_gas=True,
            device_class=SensorDeviceClass.GAS,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    MbusDeviceType.HEAT: (
        DSMRSensorEntityDescription(
            key="heat_reading",
            translation_key="heat_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_heat=True,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    MbusDeviceType.WATER: (
        DSMRSensorEntityDescription(
            key="water_reading",
            translation_key="water_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_water=True,
            device_class=SensorDeviceClass.WATER,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
    MbusDeviceType.HEAT_COOL: (
        DSMRSensorEntityDescription(
            key="heat_reading",
            translation_key="heat_meter_reading",
            obis_reference="MBUS_METER_READING",
            is_heat=True,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
    ),
}


def device_class_and_uom(
    data: Telegram | MbusDevice,
    entity_description: DSMRSensorEntityDescription,
) -> tuple[SensorDeviceClass | None, str | None]:
    """Get native unit of measurement from telegram,."""
    dsmr_object = getattr(data, entity_description.obis_reference)
    uom: str | None = dsmr_object.unit or None
    with suppress(ValueError):
        if entity_description.device_class == SensorDeviceClass.GAS and (
            enery_uom := UnitOfEnergy(str(uom))
        ):
            return (SensorDeviceClass.ENERGY, enery_uom)
    if uom in UNIT_CONVERSION:
        return (entity_description.device_class, UNIT_CONVERSION[uom])
    return (entity_description.device_class, uom)


def rename_old_gas_to_mbus(
    hass: HomeAssistant, entry: ConfigEntry, mbus_device_id: str
) -> None:
    """Rename old gas sensor to mbus variant."""
    dev_reg = dr.async_get(hass)
    for dev_id in (mbus_device_id, entry.entry_id):
        device_entry_v1 = dev_reg.async_get_device(identifiers={(DOMAIN, dev_id)})
        if device_entry_v1 is not None:
            device_id = device_entry_v1.id

            ent_reg = er.async_get(hass)
            entries = er.async_entries_for_device(ent_reg, device_id)

            for entity in entries:
                if entity.unique_id.endswith(
                    "belgium_5min_gas_meter_reading"
                ) or entity.unique_id.endswith("hourly_gas_meter_reading"):
                    if ent_reg.async_get_entity_id(
                        SENSOR_DOMAIN, DOMAIN, mbus_device_id
                    ):
                        LOGGER.debug(
                            "Skip migration of %s because it already exists",
                            entity.entity_id,
                        )
                        continue
                    new_device = dev_reg.async_get_or_create(
                        config_entry_id=entry.entry_id,
                        identifiers={(DOMAIN, mbus_device_id)},
                    )
                    ent_reg.async_update_entity(
                        entity.entity_id,
                        new_unique_id=mbus_device_id,
                        device_id=new_device.id,
                    )
                    LOGGER.debug(
                        "Migrated entity %s from unique id %s to %s",
                        entity.entity_id,
                        entity.unique_id,
                        mbus_device_id,
                    )
            # Cleanup old device
            dev_entities = er.async_entries_for_device(
                ent_reg, device_id, include_disabled_entities=True
            )
            if not dev_entities:
                dev_reg.async_remove_device(device_id)


def is_supported_description(
    data: Telegram | MbusDevice,
    description: DSMRSensorEntityDescription,
    dsmr_version: str,
) -> bool:
    """Check if this is a supported description for this telegram."""
    return hasattr(data, description.obis_reference) and (
        description.dsmr_versions is None or dsmr_version in description.dsmr_versions
    )


def create_mbus_entities(
    hass: HomeAssistant, telegram: Telegram, entry: ConfigEntry, dsmr_version: str
) -> Generator[DSMREntity]:
    """Create MBUS Entities."""
    mbus_devices: list[MbusDevice] = getattr(telegram, "MBUS_DEVICES", [])
    for device in mbus_devices:
        if (device_type := getattr(device, "MBUS_DEVICE_TYPE", None)) is None:
            continue
        type_ = int(device_type.value)

        if type_ not in SENSORS_MBUS_DEVICE_TYPE:
            LOGGER.warning("Unsupported MBUS_DEVICE_TYPE (%d)", type_)
            continue

        if identifier := getattr(device, "MBUS_EQUIPMENT_IDENTIFIER", None):
            serial_ = identifier.value
            rename_old_gas_to_mbus(hass, entry, serial_)
        else:
            serial_ = ""

        for description in SENSORS_MBUS_DEVICE_TYPE.get(type_, ()):
            if not is_supported_description(device, description, dsmr_version):
                continue
            yield DSMREntity(
                description,
                entry,
                telegram,
                *device_class_and_uom(device, description),
                serial_,
                device.channel_id,
            )


def get_dsmr_object(
    telegram: Telegram | None, mbus_id: int, obis_reference: str
) -> DSMRObject | None:
    """Extract DSMR object from telegram."""
    if not telegram:
        return None

    telegram_or_device: Telegram | MbusDevice | None = telegram
    if mbus_id:
        telegram_or_device = telegram.get_mbus_device_by_channel(mbus_id)
        if telegram_or_device is None:
            return None

    return getattr(telegram_or_device, obis_reference, None)


def _create_reader_factory(
    hass: HomeAssistant,
    entry: DsmrConfigEntry,
    telegram_callback: Callable[[Telegram | None], None],
) -> partial[Any]:
    """Create the asyncio reader factory for the configured connection.

    A port starting with "/" is a local serial device, which doesn't need a
    liveness check; anything else is a network connection that can drop
    silently, so it gets a keep-alive watchdog that closes the connection
    (triggering a reconnect) when no telegram arrives in time.
    """
    dsmr_version = entry.data[CONF_DSMR_VERSION]

    # Legacy network entries stored host and port separately; combine them into
    # the single socket://host:port form newer entries already use, in memory
    # only, so the stored entry stays untouched and rolling back to an older
    # Home Assistant version keeps working.
    port = entry.data[CONF_PORT]
    if CONF_HOST in entry.data:
        port = f"socket://{entry.data[CONF_HOST]}:{port}"

    protocol = entry.data.get(CONF_PROTOCOL, DSMR_PROTOCOL)
    if protocol == RFXTRX_DSMR_PROTOCOL:
        if port.startswith("/"):
            return partial(
                create_rfxtrx_dsmr_reader,
                port,
                dsmr_version,
                telegram_callback,
                loop=hass.loop,
            )
        # The RFXtrx serial reader has no keep-alive support, so the network
        # host and port are fed to the dedicated TCP reader instead.
        address = urlparse(port)
        return partial(
            create_rfxtrx_tcp_dsmr_reader,
            address.hostname,
            address.port,
            dsmr_version,
            telegram_callback,
            loop=hass.loop,
            keep_alive_interval=60,
        )
    # create_dsmr_reader opens both local devices and any URL (socket://,
    # esphome://, ...); the only difference is the keep-alive watchdog.
    keep_alive = {} if port.startswith("/") else {"keep_alive_interval": 60}
    return partial(
        create_dsmr_reader,
        port,
        dsmr_version,
        telegram_callback,
        loop=hass.loop,
        **keep_alive,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DsmrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DSMR sensor."""
    dsmr_version = entry.data[CONF_DSMR_VERSION]
    entities: list[DSMREntity] = []
    initialized: bool = False
    add_entities_handler: Callable[[], None] | None

    @callback
    def init_async_add_entities(telegram: Telegram) -> None:
        """Add the sensor entities after the first telegram was received."""
        nonlocal add_entities_handler
        assert add_entities_handler is not None
        add_entities_handler()
        add_entities_handler = None

        entities.extend(create_mbus_entities(hass, telegram, entry, dsmr_version))

        entities.extend(
            [
                DSMREntity(
                    description,
                    entry,
                    telegram,
                    *device_class_and_uom(telegram, description),
                )
                for description in SENSORS
                if is_supported_description(telegram, description, dsmr_version)
                and (
                    (not description.is_gas and not description.is_heat)
                    or CONF_SERIAL_ID_GAS in entry.data
                )
            ]
        )
        async_add_entities(entities)

    add_entities_handler = async_dispatcher_connect(
        hass, EVENT_FIRST_TELEGRAM.format(entry.entry_id), init_async_add_entities
    )
    min_time_between_updates = timedelta(
        seconds=entry.options.get(CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE)
    )

    @callback
    def _publish_updates(now: datetime | None = None) -> None:
        """Publish the values collected so far and update Home Assistant."""
        for entity in entities:
            if entity.calculate_value() and entity.hass:
                entity.async_write_ha_state()

    @callback
    def receive_telegram(telegram: Telegram | None) -> None:
        """Handle every new telegram and accumulate its data."""
        nonlocal initialized

        for entity in entities:
            entity.accumulate_data(telegram)

        entry.runtime_data.telegram = telegram

        if not initialized and telegram:
            initialized = True
            async_dispatcher_send(
                hass, EVENT_FIRST_TELEGRAM.format(entry.entry_id), telegram
            )

        # Publish immediately when not averaging, or on connection state change
        if not min_time_between_updates or not telegram:
            _publish_updates()

    # With an averaging window, publish on a cadence independent of telegram
    # arrival.
    if min_time_between_updates:
        entry.async_on_unload(
            async_track_time_interval(hass, _publish_updates, min_time_between_updates)
        )

    # Creates an asyncio.Protocol factory for reading DSMR telegrams from the
    # connection and calls receive_telegram to update entities on arrival
    reader_factory = _create_reader_factory(hass, entry, receive_telegram)

    async def connect_and_reconnect() -> None:
        """Connect to DSMR and keep reconnecting until Home Assistant stops."""
        stop_listener = None
        transport = None
        protocol = None

        while hass.state is CoreState.not_running or hass.is_running:
            # Start DSMR asyncio.Protocol reader

            # Reflect connected state in devices state by setting an
            # empty telegram resulting in `unknown` states
            receive_telegram({})

            try:
                transport, protocol = await reader_factory()

                if transport:
                    # Register listener to close transport on HA shutdown
                    @callback
                    def close_transport(_event: Event) -> None:
                        """Close the transport on HA shutdown."""
                        if not transport:  # noqa: B023
                            return
                        transport.close()  # noqa: B023

                    stop_listener = hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STOP, close_transport
                    )

                    # Wait for reader to close
                    await protocol.wait_closed()

                    # Unexpected disconnect
                    if hass.state is CoreState.not_running or hass.is_running:
                        stop_listener()

                transport = None
                protocol = None

                # Reflect disconnect state in devices state by setting an
                # None telegram resulting in `unavailable` states
                receive_telegram(None)

                # throttle reconnect attempts
                await asyncio.sleep(DEFAULT_RECONNECT_INTERVAL)

            except OSError:
                # Log any error while establishing connection and drop to retry
                # connection wait
                LOGGER.exception("Error connecting to DSMR")
                transport = None
                protocol = None

                # Reflect disconnect state in devices state by setting an
                # None telegram resulting in `unavailable` states
                receive_telegram(None)

                # throttle reconnect attempts
                await asyncio.sleep(DEFAULT_RECONNECT_INTERVAL)
            except CancelledError:
                # Reflect disconnect state in devices state by setting an
                # None telegram resulting in `unavailable` states
                receive_telegram(None)

                if stop_listener and (
                    hass.state is CoreState.not_running or hass.is_running
                ):
                    stop_listener()

                if transport:
                    transport.close()

                if protocol:
                    await protocol.wait_closed()

                return

    # Can't be hass.async_add_job because job runs forever
    task = asyncio.create_task(connect_and_reconnect())

    @callback
    def _async_stop(_: Event) -> None:
        if add_entities_handler is not None:
            add_entities_handler()
        task.cancel()

    # Make sure task is cancelled on shutdown (or tests complete)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )

    # Save the task to be able to cancel it when unloading
    entry.runtime_data.task = task


class DSMREntity(SensorEntity):
    """Entity reading values from DSMR telegram."""

    entity_description: DSMRSensorEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entity_description: DSMRSensorEntityDescription,
        entry: ConfigEntry,
        telegram: Telegram,
        device_class: SensorDeviceClass | None,
        native_unit_of_measurement: str | None,
        serial_id: str = "",
        mbus_id: int = 0,
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self.telegram: Telegram | None = telegram
        self._dsmr_version = entry.data[CONF_DSMR_VERSION]
        self._value: StateType = None
        self._available: bool = True
        self._pending_publish: bool = False

        # Only average when a non-zero update interval is configured
        self._is_averaged_sensor = entity_description.average and bool(
            entry.options.get(CONF_TIME_BETWEEN_UPDATE, DEFAULT_TIME_BETWEEN_UPDATE)
        )
        self._value_sum: Decimal = Decimal(0)
        self._value_count: int = 0

        device_serial = entry.data[CONF_SERIAL_ID]
        device_name = DEVICE_NAME_ELECTRICITY
        if entity_description.is_gas:
            if serial_id:
                device_serial = serial_id
            else:
                device_serial = entry.data[CONF_SERIAL_ID_GAS]
            device_name = DEVICE_NAME_GAS
        if entity_description.is_water:
            if serial_id:
                device_serial = serial_id
            device_name = DEVICE_NAME_WATER
        if entity_description.is_heat:
            if serial_id:
                device_serial = serial_id
            device_name = DEVICE_NAME_HEAT
        if device_serial is None:
            device_serial = entry.entry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_serial)},
            name=device_name,
        )
        self._mbus_id = mbus_id
        if mbus_id != 0:
            if serial_id:
                self._attr_unique_id = f"{device_serial}"
            else:
                self._attr_unique_id = f"{device_serial}_{mbus_id}"
        else:
            self._attr_unique_id = f"{device_serial}_{entity_description.key}"

        self.accumulate_data(telegram)
        self.calculate_value()

    @callback
    def accumulate_data(self, telegram: Telegram | None) -> None:
        """Store the telegram and update the value from it.

        Non-averaged sensors cache their reading as soon as the object appears,
        so a later partial telegram that omits it cannot drop the value at
        publish time. Averaged sensors keep a running sum and count instead.
        """
        self.telegram = telegram

        if not telegram:
            self._reset_average()
            self._pending_publish = True
            return

        dsmr_object = get_dsmr_object(
            telegram, self._mbus_id, self.entity_description.obis_reference
        )
        if dsmr_object is None or dsmr_object.value is None:
            return

        if not self._is_averaged_sensor:
            self._value = self._convert_value(dsmr_object.value)
            self._pending_publish = True
            return

        try:
            value = Decimal(dsmr_object.value)
        except (ArithmeticError, TypeError, ValueError) as err:
            LOGGER.debug(
                "Could not convert %s value %s for averaging: %s",
                self.entity_description.key,
                dsmr_object.value,
                err,
            )
            return

        self._value_sum += value
        self._value_count += 1

    @callback
    def _reset_average(self) -> None:
        """Reset the running average accumulator."""
        self._value_sum = Decimal(0)
        self._value_count = 0

    @callback
    def calculate_value(self) -> bool:
        """Recalculate the value to report from the data collected so far.

        Return True when the state must be published: non-averaged sensors only
        after a new reading or a connection state change, so timer ticks do not
        rewrite an unchanged cached value (which would fire spurious events for
        force_update sensors); averaged sensors on every tick, as their mean or
        availability changes with each window.
        """
        pending = self._pending_publish
        self._pending_publish = False

        # A missing telegram marks the entity unavailable; an empty telegram
        # (just (re)connected, no data yet) reports unknown. Either way drop any
        # partially accumulated average.
        if not self.telegram:
            self._reset_average()
            self._value = None
            self._available = self.telegram is not None
            return pending

        # Non-averaged sensors cache their latest value in accumulate_data as
        # telegrams arrive, so it is already up to date and survives a partial
        # telegram that omits the object.
        if not self._is_averaged_sensor:
            self._available = True
            return pending

        # Averaged sensors report the mean of the values collected during the
        # interval; with no readings collected the sensor is unavailable.
        self._available = bool(self._value_count)
        if self._value_count:
            self._value = round(
                float(self._value_sum / self._value_count), DEFAULT_PRECISION
            )
        self._reset_average()
        return True

    def _convert_value(self, value: str | float) -> StateType:
        """Convert a raw telegram reading into the value reported by the sensor."""
        if self.entity_description.obis_reference == "ELECTRICITY_ACTIVE_TARIFF":
            return self.translate_tariff(str(value), self._dsmr_version)

        with suppress(TypeError, ValueError):
            value = round(float(value), DEFAULT_PRECISION)

        # Make sure we do not return a zero value for an energy sensor
        if not value and self.state_class == SensorStateClass.TOTAL_INCREASING:
            return None
        return value

    @property
    @override
    def available(self) -> bool:
        """Return whether the last publish produced a value to report."""
        return self._available

    @property
    @override
    def native_value(self) -> StateType:
        """Return the calculated state of sensor."""
        return self._value

    @staticmethod
    def translate_tariff(value: str, dsmr_version: str) -> str | None:
        """Convert 2/1 to normal/low depending on DSMR version."""
        # DSMR V5B: Note: In Belgium values are swapped:
        # DSMR V5EONHU: Note: In EON HUngary values are swapped:
        # Rate code 2 is used for low rate and rate code 1 is used for normal rate.
        if dsmr_version in ("5B", "5EONHU"):
            if value == "0001":
                value = "0002"
            elif value == "0002":
                value = "0001"
        # DSMR V2.2: Note: Rate code 1 is used for low rate and rate code 2 is
        # used for normal rate.
        if value == "0002":
            return "normal"
        if value == "0001":
            return "low"

        return None
