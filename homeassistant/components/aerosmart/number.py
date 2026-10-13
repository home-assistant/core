"""Number platform for aerosmart (writable setpoints).

Every entity here is disabled by default: writability was inferred from the
source register's name, not a manufacturer specification, and must be
verified against the real unit before being relied on.
"""

from dataclasses import dataclass
from typing import cast, override

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AerosmartConfigEntry
from .entity import AerosmartEntity

# Coordinator-based (all entities share one poll); parallel per-entity
# writes to the same Modbus link would race, so keep this serialized.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AerosmartNumberEntityDescription(NumberEntityDescription):
    """Describes an aerosmart number entity."""

    component: str
    attribute: str


NUMBER_DESCRIPTIONS: tuple[AerosmartNumberEntityDescription, ...] = (
    AerosmartNumberEntityDescription(
        key="boost_functions_ventilation_zeitspanne_function_heizung_plus",
        translation_key="boost_functions_ventilation_zeitspanne_function_heizung_plus",
        entity_category=EntityCategory.CONFIG,
        component="boost_functions_ventilation",
        attribute="zeitspanne_function_heizung_plus",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="min",
        native_min_value=30,
        native_max_value=240,
        native_step=1,
    ),
    AerosmartNumberEntityDescription(
        key="boost_functions_ventilation_sollwert_erhoehung_function_heizung_plus",
        translation_key="boost_functions_ventilation_sollwert_erhoehung_function_heizung_plus",
        entity_category=EntityCategory.CONFIG,
        component="boost_functions_ventilation",
        attribute="sollwert_erhoehung_function_heizung_plus",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="K",
        native_min_value=0.3,
        native_max_value=2.0,
    ),
    AerosmartNumberEntityDescription(
        key="boost_functions_ventilation_zeitspanne_function_party",
        translation_key="boost_functions_ventilation_zeitspanne_function_party",
        entity_category=EntityCategory.CONFIG,
        component="boost_functions_ventilation",
        attribute="zeitspanne_function_party",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="min",
        native_min_value=60,
        native_max_value=240,
        native_step=1,
    ),
    AerosmartNumberEntityDescription(
        key="ventilation_erhoehung_luefterstufe_3",
        translation_key="ventilation_erhoehung_luefterstufe_3",
        entity_category=EntityCategory.CONFIG,
        component="ventilation",
        attribute="erhoehung_luefterstufe_3",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="%",
        native_min_value=30,
        native_max_value=100,
    ),
    AerosmartNumberEntityDescription(
        key="ventilation_soll_volumenstrom_luefterstufe2",
        translation_key="ventilation_soll_volumenstrom_luefterstufe2",
        entity_category=EntityCategory.CONFIG,
        component="ventilation",
        attribute="soll_volumenstrom_luefterstufe2",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="m³/h",
        native_min_value=40,
        native_max_value=300,
    ),
    AerosmartNumberEntityDescription(
        key="room_temperature_temp_raumluft_soll",
        translation_key="room_temperature_temp_raumluft_soll",
        entity_category=EntityCategory.CONFIG,
        component="room_temperature",
        attribute="temp_raumluft_soll",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="°C",
        native_min_value=14.0,
        native_max_value=26.0,
    ),
    AerosmartNumberEntityDescription(
        key="summer_bypass_sommerautomatik_schaltpunkt1",
        translation_key="summer_bypass_sommerautomatik_schaltpunkt1",
        entity_category=EntityCategory.CONFIG,
        component="summer_bypass",
        attribute="sommerautomatik_schaltpunkt1",
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=2400,
    ),
    AerosmartNumberEntityDescription(
        key="summer_bypass_sommerautomatik_schaltpunkt2",
        translation_key="summer_bypass_sommerautomatik_schaltpunkt2",
        entity_category=EntityCategory.CONFIG,
        component="summer_bypass",
        attribute="sommerautomatik_schaltpunkt2",
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=2400,
    ),
    AerosmartNumberEntityDescription(
        key="summer_bypass_sommerautomatik_schaltpunkt3",
        translation_key="summer_bypass_sommerautomatik_schaltpunkt3",
        entity_category=EntityCategory.CONFIG,
        component="summer_bypass",
        attribute="sommerautomatik_schaltpunkt3",
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=2400,
    ),
    AerosmartNumberEntityDescription(
        key="summer_bypass_sommerautomatik_schaltpunkt4",
        translation_key="summer_bypass_sommerautomatik_schaltpunkt4",
        entity_category=EntityCategory.CONFIG,
        component="summer_bypass",
        attribute="sommerautomatik_schaltpunkt4",
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=2400,
    ),
    AerosmartNumberEntityDescription(
        key="hot_water_heat_pump_wp_brauchwasser_soll_temp",
        translation_key="hot_water_heat_pump_wp_brauchwasser_soll_temp",
        entity_category=EntityCategory.CONFIG,
        component="hot_water_heat_pump",
        attribute="wp_brauchwasser_soll_temp",
        entity_registry_enabled_default=False,
        native_unit_of_measurement="°C",
        native_min_value=20.0,
        native_max_value=55.0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AerosmartConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up aerosmart numbers."""
    runtime = entry.runtime_data
    async_add_entities(
        AerosmartNumber(runtime.coordinator_for(description.component), description)
        for description in NUMBER_DESCRIPTIONS
    )


class AerosmartNumber(AerosmartEntity, NumberEntity):
    """A writable aerosmart setpoint."""

    entity_description: AerosmartNumberEntityDescription

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the register's current value."""
        value = cast(
            float | int | None,
            getattr(self._subsystem, self.entity_description.attribute),
        )
        if value is not None and self.entity_description.native_step == 1:
            # Registers documented in whole minutes use a rounded decimal
            # scale for 1/60; hide its tiny binary floating-point residue.
            return round(value)
        return value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the new setpoint and refresh."""
        await self._subsystem.write(self.entity_description.attribute, value)
        await self.coordinator.async_refresh()
