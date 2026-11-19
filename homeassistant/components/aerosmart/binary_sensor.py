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
from .entity import AerosmartEntity, AerosmartEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AerosmartBinarySensorEntityDescription(
    BinarySensorEntityDescription, AerosmartEntityDescription
):
    """Describe an aerosmart boolean holding register."""

    component: str
    attribute: str


def _description(
    component: str,
    attribute: str,
    *,
    device_class: BinarySensorDeviceClass | None = None,
    entity_category: EntityCategory | None = None,
    entity_registry_enabled_default: bool = True,
) -> AerosmartBinarySensorEntityDescription:
    """Create a binary sensor description with its derived entity keys."""
    key = f"{component}_{attribute}"
    return AerosmartBinarySensorEntityDescription(
        key=key,
        translation_key=key,
        component=component,
        attribute=attribute,
        device_class=device_class,
        entity_category=entity_category,
        entity_registry_enabled_default=entity_registry_enabled_default,
    )


BINARY_SENSOR_DESCRIPTIONS: tuple[AerosmartBinarySensorEntityDescription, ...] = (
    _description(
        component="general",
        attribute="relaykontakt_ext_lu",
    ),
    _description(
        component="outside_temperature",
        attribute="aussenluftfuehler_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="outside_temperature",
        attribute="stoerung_temperaturfuehler_aussenluft",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="outside_temperature",
        attribute="stoerung_temperaturfuehler_sole_aussenluft",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="fire_alarm",
        attribute="brandmeldealarm",
    ),
    _description(
        component="fire_alarm",
        attribute="brandmeldealarm_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="fire_alarm",
        attribute="kontakt_brandmeldealarm",
    ),
    _description(
        component="carbon_dioxide",
        attribute="co2_sensor_available",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="carbon_dioxide",
        attribute="stoerung_co2_sensor",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="utility_lockout",
        attribute="evu_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="utility_lockout",
        attribute="evu_sperre_brauchwasser_aktiv",
    ),
    _description(
        component="utility_lockout",
        attribute="evu_sperre_elektroheizstab_aktiv",
    ),
    _description(
        component="utility_lockout",
        attribute="evu_sperre_raumheizung_aktiv",
    ),
    _description(
        component="fine_dust_filter",
        attribute="feinstaubfilter_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="fine_dust_filter",
        attribute="feinstaubfilter_wechseln",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="coarse_dust_filter",
        attribute="grobstaubfilter_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="coarse_dust_filter",
        attribute="grobstaubfilter_wechseln",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="cooling",
        attribute="kuehlung_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    _description(
        component="ventilation",
        attribute="anforderung_abtauen",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="ventilation",
        attribute="anforderung_beschattung",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="ventilation",
        attribute="anforderung_st3_ext",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="ventilation",
        attribute="stoerung_teilnehmer_nicht_erreichbar",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="ventilation",
        attribute="stoerung_temperaturfuehler_verdampferregister",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="ventilation",
        attribute="stoerung_waermepumpe_hochdruck",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="ventilation",
        attribute="stoerung_waermepumpe_niederdruck",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="ventilation",
        attribute="stoerung_wert_nicht_zulaessig",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="room_temperature",
        attribute="stoerung_temperaturfuehler_raum",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="room_temperature",
        attribute="timeout_soll_temp_raum",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="room_temperature",
        attribute="timeout_temp_fuehler_raum",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="room_temperature",
        attribute="anforderung_raum_heizstufe_1",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="room_temperature",
        attribute="anforderung_raum_heizstufe_2",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="summer_bypass",
        attribute="anforderung_sommerautomatik",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="summer_bypass",
        attribute="function_sommerautomatik",
    ),
    _description(
        component="aggregate_fault",
        attribute="stoerung_summenstoerung",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="aggregate_fault",
        attribute="stoerung_summenstoerung2",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="fans",
        attribute="anforderung_ventilatoren_durch_waermepumpe",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="fans",
        attribute="anforderung_ventilatoren_durch_zonenregelung",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="fans",
        attribute="stoerung_zuluftventilator",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="fans",
        attribute="stoerung_abluftventilator",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="heat_pump",
        attribute="wp_kontakt_evu",
    ),
    _description(
        component="heat_pump",
        attribute="wp_relaiskontakt_ext",
    ),
    _description(
        component="hot_water_ventilation",
        attribute="anforderung_disbalance_boilerueberwaermung",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="hot_water_ventilation",
        attribute="stoerung_elektroheizstab",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="hot_water_ventilation",
        attribute="stoerung_boilerfuehler_waermepumpe",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="hot_water_ventilation",
        attribute="stoerung_boiler_uebertemperatur",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    _description(
        component="hot_water_ventilation",
        attribute="anforderung_brauchwasserheizung_elektroheizstab",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="hot_water_ventilation",
        attribute="anforderung_brauchwasserheizung_waermepumpe",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _description(
        component="hot_water_heat_pump",
        attribute="wp_elektroheizstab_vorhanden",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
        component = getattr(self.coordinator.device, self.entity_description.component)
        value = getattr(component, self.entity_description.attribute)
        return None if value is None else bool(value)
