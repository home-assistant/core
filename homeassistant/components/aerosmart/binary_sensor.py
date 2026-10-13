"""Binary sensor platform for aerosmart."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AerosmartConfigEntry
from .entity import AerosmartEntity

# Coordinator-based (all entities share one poll); parallel per-entity
# writes to the same Modbus link would race, so keep this serialized.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AerosmartBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an aerosmart binary_sensor entity.

    The underlying register is a plain holding register, not a native Modbus
    coil -- ``is_on`` treats any non-zero value as True. This is a naming
    heuristic against an unverified register map, not a confirmed
    manufacturer specification.
    """

    component: str
    attribute: str


BINARY_SENSOR_DESCRIPTIONS: tuple[AerosmartBinarySensorEntityDescription, ...] = (
    AerosmartBinarySensorEntityDescription(
        key="general_relaykontakt_ext_lu",
        translation_key="general_relaykontakt_ext_lu",
        component="general",
        attribute="relaykontakt_ext_lu",
    ),
    AerosmartBinarySensorEntityDescription(
        key="outside_temperature_aussenluftfuehler_vorhanden",
        translation_key="outside_temperature_aussenluftfuehler_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="outside_temperature",
        attribute="aussenluftfuehler_vorhanden",
    ),
    AerosmartBinarySensorEntityDescription(
        key="outside_temperature_stoerung_temperaturfuehler_aussenluft",
        translation_key="outside_temperature_stoerung_temperaturfuehler_aussenluft",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="outside_temperature",
        attribute="stoerung_temperaturfuehler_aussenluft",
    ),
    AerosmartBinarySensorEntityDescription(
        key="outside_temperature_stoerung_temperaturfuehler_sole_aussenluft",
        translation_key="outside_temperature_stoerung_temperaturfuehler_sole_aussenluft",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="outside_temperature",
        attribute="stoerung_temperaturfuehler_sole_aussenluft",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fire_alarm_brandmeldealarm",
        translation_key="fire_alarm_brandmeldealarm",
        component="fire_alarm",
        attribute="brandmeldealarm",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fire_alarm_brandmeldealarm_vorhanden",
        translation_key="fire_alarm_brandmeldealarm_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="fire_alarm",
        attribute="brandmeldealarm_vorhanden",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fire_alarm_kontakt_brandmeldealarm",
        translation_key="fire_alarm_kontakt_brandmeldealarm",
        component="fire_alarm",
        attribute="kontakt_brandmeldealarm",
    ),
    AerosmartBinarySensorEntityDescription(
        key="carbon_dioxide_co2_sensor_available",
        translation_key="carbon_dioxide_co2_sensor_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="carbon_dioxide",
        attribute="co2_sensor_available",
    ),
    AerosmartBinarySensorEntityDescription(
        key="carbon_dioxide_stoerung_co2_sensor",
        translation_key="carbon_dioxide_stoerung_co2_sensor",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="carbon_dioxide",
        attribute="stoerung_co2_sensor",
    ),
    AerosmartBinarySensorEntityDescription(
        key="utility_lockout_evu_vorhanden",
        translation_key="utility_lockout_evu_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="utility_lockout",
        attribute="evu_vorhanden",
    ),
    AerosmartBinarySensorEntityDescription(
        key="utility_lockout_evu_sperre_brauchwasser_aktiv",
        translation_key="utility_lockout_evu_sperre_brauchwasser_aktiv",
        component="utility_lockout",
        attribute="evu_sperre_brauchwasser_aktiv",
    ),
    AerosmartBinarySensorEntityDescription(
        key="utility_lockout_evu_sperre_elektroheizstab_aktiv",
        translation_key="utility_lockout_evu_sperre_elektroheizstab_aktiv",
        component="utility_lockout",
        attribute="evu_sperre_elektroheizstab_aktiv",
    ),
    AerosmartBinarySensorEntityDescription(
        key="utility_lockout_evu_sperre_raumheizung_aktiv",
        translation_key="utility_lockout_evu_sperre_raumheizung_aktiv",
        component="utility_lockout",
        attribute="evu_sperre_raumheizung_aktiv",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fine_dust_filter_feinstaubfilter_vorhanden",
        translation_key="fine_dust_filter_feinstaubfilter_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="fine_dust_filter",
        attribute="feinstaubfilter_vorhanden",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fine_dust_filter_feinstaubfilter_wechseln",
        translation_key="fine_dust_filter_feinstaubfilter_wechseln",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="fine_dust_filter",
        attribute="feinstaubfilter_wechseln",
    ),
    AerosmartBinarySensorEntityDescription(
        key="coarse_dust_filter_grobstaubfilter_vorhanden",
        translation_key="coarse_dust_filter_grobstaubfilter_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="coarse_dust_filter",
        attribute="grobstaubfilter_vorhanden",
    ),
    AerosmartBinarySensorEntityDescription(
        key="coarse_dust_filter_grobstaubfilter_wechseln",
        translation_key="coarse_dust_filter_grobstaubfilter_wechseln",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="coarse_dust_filter",
        attribute="grobstaubfilter_wechseln",
    ),
    AerosmartBinarySensorEntityDescription(
        key="cooling_kuehlung_vorhanden",
        translation_key="cooling_kuehlung_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="cooling",
        attribute="kuehlung_vorhanden",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_anforderung_abtauen",
        translation_key="ventilation_anforderung_abtauen",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="ventilation",
        attribute="anforderung_abtauen",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_anforderung_beschattung",
        translation_key="ventilation_anforderung_beschattung",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="ventilation",
        attribute="anforderung_beschattung",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_anforderung_st3_ext",
        translation_key="ventilation_anforderung_st3_ext",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="ventilation",
        attribute="anforderung_st3_ext",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_stoerung_teilnehmer_nicht_erreichbar",
        translation_key="ventilation_stoerung_teilnehmer_nicht_erreichbar",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="ventilation",
        attribute="stoerung_teilnehmer_nicht_erreichbar",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_stoerung_temperaturfuehler_verdampferregister",
        translation_key="ventilation_stoerung_temperaturfuehler_verdampferregister",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="ventilation",
        attribute="stoerung_temperaturfuehler_verdampferregister",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_stoerung_waermepumpe_hochdruck",
        translation_key="ventilation_stoerung_waermepumpe_hochdruck",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="ventilation",
        attribute="stoerung_waermepumpe_hochdruck",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_stoerung_waermepumpe_niederdruck",
        translation_key="ventilation_stoerung_waermepumpe_niederdruck",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="ventilation",
        attribute="stoerung_waermepumpe_niederdruck",
    ),
    AerosmartBinarySensorEntityDescription(
        key="ventilation_stoerung_wert_nicht_zulaessig",
        translation_key="ventilation_stoerung_wert_nicht_zulaessig",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="ventilation",
        attribute="stoerung_wert_nicht_zulaessig",
    ),
    AerosmartBinarySensorEntityDescription(
        key="room_temperature_stoerung_temperaturfuehler_raum",
        translation_key="room_temperature_stoerung_temperaturfuehler_raum",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="room_temperature",
        attribute="stoerung_temperaturfuehler_raum",
    ),
    AerosmartBinarySensorEntityDescription(
        key="room_temperature_timeout_soll_temp_raum",
        translation_key="room_temperature_timeout_soll_temp_raum",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="room_temperature",
        attribute="timeout_soll_temp_raum",
    ),
    AerosmartBinarySensorEntityDescription(
        key="room_temperature_timeout_temp_fuehler_raum",
        translation_key="room_temperature_timeout_temp_fuehler_raum",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="room_temperature",
        attribute="timeout_temp_fuehler_raum",
    ),
    AerosmartBinarySensorEntityDescription(
        key="room_temperature_anforderung_raum_heizstufe_1",
        translation_key="room_temperature_anforderung_raum_heizstufe_1",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="room_temperature",
        attribute="anforderung_raum_heizstufe_1",
    ),
    AerosmartBinarySensorEntityDescription(
        key="room_temperature_anforderung_raum_heizstufe_2",
        translation_key="room_temperature_anforderung_raum_heizstufe_2",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="room_temperature",
        attribute="anforderung_raum_heizstufe_2",
    ),
    AerosmartBinarySensorEntityDescription(
        key="summer_bypass_anforderung_sommerautomatik",
        translation_key="summer_bypass_anforderung_sommerautomatik",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="summer_bypass",
        attribute="anforderung_sommerautomatik",
    ),
    AerosmartBinarySensorEntityDescription(
        key="summer_bypass_function_sommerautomatik",
        translation_key="summer_bypass_function_sommerautomatik",
        component="summer_bypass",
        attribute="function_sommerautomatik",
    ),
    AerosmartBinarySensorEntityDescription(
        key="aggregate_fault_stoerung_summenstoerung",
        translation_key="aggregate_fault_stoerung_summenstoerung",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="aggregate_fault",
        attribute="stoerung_summenstoerung",
    ),
    AerosmartBinarySensorEntityDescription(
        key="aggregate_fault_stoerung_summenstoerung2",
        translation_key="aggregate_fault_stoerung_summenstoerung2",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="aggregate_fault",
        attribute="stoerung_summenstoerung2",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fans_anforderung_ventilatoren_durch_waermepumpe",
        translation_key="fans_anforderung_ventilatoren_durch_waermepumpe",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="fans",
        attribute="anforderung_ventilatoren_durch_waermepumpe",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fans_anforderung_ventilatoren_durch_zonenregelung",
        translation_key="fans_anforderung_ventilatoren_durch_zonenregelung",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="fans",
        attribute="anforderung_ventilatoren_durch_zonenregelung",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fans_stoerung_zuluftventilator",
        translation_key="fans_stoerung_zuluftventilator",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="fans",
        attribute="stoerung_zuluftventilator",
    ),
    AerosmartBinarySensorEntityDescription(
        key="fans_stoerung_abluftventilator",
        translation_key="fans_stoerung_abluftventilator",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="fans",
        attribute="stoerung_abluftventilator",
    ),
    AerosmartBinarySensorEntityDescription(
        key="heat_pump_wp_kontakt_evu",
        translation_key="heat_pump_wp_kontakt_evu",
        component="heat_pump",
        attribute="wp_kontakt_evu",
    ),
    AerosmartBinarySensorEntityDescription(
        key="heat_pump_wp_relaiskontakt_ext",
        translation_key="heat_pump_wp_relaiskontakt_ext",
        component="heat_pump",
        attribute="wp_relaiskontakt_ext",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_ventilation_anforderung_disbalance_boilerueberwaermung",
        translation_key="hot_water_ventilation_anforderung_disbalance_boilerueberwaermung",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="hot_water_ventilation",
        attribute="anforderung_disbalance_boilerueberwaermung",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_ventilation_stoerung_elektroheizstab",
        translation_key="hot_water_ventilation_stoerung_elektroheizstab",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="hot_water_ventilation",
        attribute="stoerung_elektroheizstab",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_ventilation_stoerung_boilerfuehler_waermepumpe",
        translation_key="hot_water_ventilation_stoerung_boilerfuehler_waermepumpe",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="hot_water_ventilation",
        attribute="stoerung_boilerfuehler_waermepumpe",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_ventilation_stoerung_boiler_uebertemperatur",
        translation_key="hot_water_ventilation_stoerung_boiler_uebertemperatur",
        device_class=BinarySensorDeviceClass.PROBLEM,
        component="hot_water_ventilation",
        attribute="stoerung_boiler_uebertemperatur",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_ventilation_anforderung_brauchwasserheizung_elektroheizstab",
        translation_key="hot_water_ventilation_anforderung_brauchwasserheizung_elektroheizstab",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="hot_water_ventilation",
        attribute="anforderung_brauchwasserheizung_elektroheizstab",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_ventilation_anforderung_brauchwasserheizung_waermepumpe",
        translation_key="hot_water_ventilation_anforderung_brauchwasserheizung_waermepumpe",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="hot_water_ventilation",
        attribute="anforderung_brauchwasserheizung_waermepumpe",
    ),
    AerosmartBinarySensorEntityDescription(
        key="hot_water_heat_pump_wp_elektroheizstab_vorhanden",
        translation_key="hot_water_heat_pump_wp_elektroheizstab_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        component="hot_water_heat_pump",
        attribute="wp_elektroheizstab_vorhanden",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AerosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aerosmart binary sensors."""
    runtime = entry.runtime_data
    async_add_entities(
        AerosmartBinarySensor(
            runtime.coordinator_for(description.component), description
        )
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class AerosmartBinarySensor(AerosmartEntity, BinarySensorEntity):
    """An aerosmart binary_sensor entity backed by a single register."""

    entity_description: AerosmartBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the register's value is non-zero."""
        value = getattr(self._subsystem, self.entity_description.attribute)
        return None if value is None else bool(value)
