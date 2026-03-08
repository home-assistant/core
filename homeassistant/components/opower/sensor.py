"""Support for Opower sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from opower import MeterType, UnitOfMeasure

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpowerConfigEntry, OpowerCoordinator, OpowerData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpowerEntityDescription(SensorEntityDescription):
    """Class describing Opower sensors entities."""

    value_fn: Callable[[OpowerData], str | float | date | datetime | None]


COMMON_SENSORS: tuple[OpowerEntityDescription, ...] = (
    OpowerEntityDescription(
        key="last_changed",
        translation_key="last_changed",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_changed,
    ),
    OpowerEntityDescription(
        key="last_updated",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_updated,
    ),
)

# suggested_display_precision=0 for all sensors since
# Opower provides 0 decimal points for all these.
# (for the statistics in the energy dashboard Opower does provide decimal points)
ELEC_SENSORS: tuple[OpowerEntityDescription, ...] = (
    OpowerEntityDescription(
        key="elec_usage_to_date",
        translation_key="elec_usage_to_date",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        # Not TOTAL_INCREASING because it can decrease for accounts with solar
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.usage_to_date if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_forecasted_usage",
        translation_key="elec_forecasted_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.forecasted_usage if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_typical_usage",
        translation_key="elec_typical_usage",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.typical_usage if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_cost_to_date",
        translation_key="elec_cost_to_date",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.cost_to_date if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_forecasted_cost",
        translation_key="elec_forecasted_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.forecasted_cost if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_typical_cost",
        translation_key="elec_typical_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.typical_cost if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_start_date",
        translation_key="elec_start_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.forecast.start_date if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="elec_end_date",
        translation_key="elec_end_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.forecast.end_date if data.forecast else None,
    ),
)
GAS_SENSORS: tuple[OpowerEntityDescription, ...] = (
    OpowerEntityDescription(
        key="gas_usage_to_date",
        translation_key="gas_usage_to_date",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.usage_to_date if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_forecasted_usage",
        translation_key="gas_forecasted_usage",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.forecasted_usage if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_typical_usage",
        translation_key="gas_typical_usage",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CENTUM_CUBIC_FEET,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.typical_usage if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_cost_to_date",
        translation_key="gas_cost_to_date",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.cost_to_date if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_forecasted_cost",
        translation_key="gas_forecasted_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.forecasted_cost if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_typical_cost",
        translation_key="gas_typical_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="USD",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=0,
        value_fn=lambda data: data.forecast.typical_cost if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_start_date",
        translation_key="gas_start_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.forecast.start_date if data.forecast else None,
    ),
    OpowerEntityDescription(
        key="gas_end_date",
        translation_key="gas_end_date",
        device_class=SensorDeviceClass.DATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.forecast.end_date if data.forecast else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Opower sensor."""
    coordinator = entry.runtime_data
    added_accounts: set[str] = set()

    @callback
    def _update_entities() -> None:
        """Update entities."""
        new_entities: list[OpowerSensor] = []
        current_accounts = set(coordinator.data)

        for account_id, opower_data in coordinator.data.items():
            if account_id in added_accounts:
                continue

            added_accounts.add(account_id)
            account = opower_data.account
            forecast = opower_data.forecast
            device_id = (
                f"{coordinator.api.utility.subdomain()}_{account.utility_account_id}"
            )
            device = DeviceInfo(
                identifiers={(DOMAIN, device_id)},
                name=f"{account.meter_type.name} account {account.utility_account_id}",
                manufacturer="Opower",
                model=coordinator.api.utility.name(),
                entry_type=DeviceEntryType.SERVICE,
            )
            sensors: tuple[OpowerEntityDescription, ...] = COMMON_SENSORS
            if (
                account.meter_type == MeterType.ELEC
                and forecast is not None
                and forecast.unit_of_measure == UnitOfMeasure.KWH
            ):
                sensors += ELEC_SENSORS
            elif (
                account.meter_type == MeterType.GAS
                and forecast is not None
                and forecast.unit_of_measure in [UnitOfMeasure.THERM, UnitOfMeasure.CCF]
            ):
                sensors += GAS_SENSORS
            new_entities.extend(
                OpowerSensor(
                    coordinator,
                    sensor,
                    account.utility_account_id,
                    device,
                    device_id,
                )
                for sensor in sensors
            )

        if new_entities:
            async_add_entities(new_entities)

        stale_accounts = added_accounts - current_accounts
        if stale_accounts:
            device_registry = dr.async_get(hass)
            entity_registry = er.async_get(hass)
            for account_id in stale_accounts:
                device_id = f"{coordinator.api.utility.subdomain()}_{account_id}"
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                )
                if device_entry:
                    for entity_entry in er.async_entries_for_device(
                        entity_registry, device_entry.id, include_disabled_entities=True
                    ):
                        entity_registry.async_remove(entity_entry.entity_id)
                    device_registry.async_update_device(
                        device_entry.id, remove_config_entry_id=entry.entry_id
                    )
            added_accounts.difference_update(stale_accounts)

    _update_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_entities))


class OpowerSensor(CoordinatorEntity[OpowerCoordinator], SensorEntity):
    """Representation of an Opower sensor."""

    _attr_has_entity_name = True
    entity_description: OpowerEntityDescription

    def __init__(
        self,
        coordinator: OpowerCoordinator,
        description: OpowerEntityDescription,
        utility_account_id: str,
        device: DeviceInfo,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = device
        self.utility_account_id = utility_account_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.utility_account_id in self.coordinator.data

    @property
    def native_value(self) -> StateType | date | datetime:
        """Return the state."""
        return self.entity_description.value_fn(
            self.coordinator.data[self.utility_account_id]
        )
