"""Support for SolarEdge Modbus number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from solaredged import ExportControl, PowerControl, StorageControl

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SolarEdgeModbusConfigEntry
from .entity import ControlComponent, SolarEdgeModbusControlEntity
from .helpers import solaredge_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SolarEdgeModbusNumberEntityDescription[ComponentT](NumberEntityDescription):
    """Describes a SolarEdge Modbus number entity."""

    value_fn: Callable[[ComponentT], float | None]
    set_fn: Callable[[ComponentT, float], Awaitable[Any]]


STORAGE_NUMBERS: tuple[SolarEdgeModbusNumberEntityDescription[StorageControl], ...] = (
    SolarEdgeModbusNumberEntityDescription(
        key="backup_reserve",
        translation_key="backup_reserve",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=lambda storage: storage.backup_reserve,
        set_fn=lambda storage, value: storage.set_backup_reserve(value),
    ),
    SolarEdgeModbusNumberEntityDescription(
        key="charge_limit",
        translation_key="charge_limit",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=1_000_000,
        native_step=1,
        value_fn=lambda storage: storage.charge_limit,
        set_fn=lambda storage, value: storage.set_charge_limit(value),
    ),
    SolarEdgeModbusNumberEntityDescription(
        key="discharge_limit",
        translation_key="discharge_limit",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=1_000_000,
        native_step=1,
        value_fn=lambda storage: storage.discharge_limit,
        set_fn=lambda storage, value: storage.set_discharge_limit(value),
    ),
)

EXPORT_NUMBERS: tuple[SolarEdgeModbusNumberEntityDescription[ExportControl], ...] = (
    SolarEdgeModbusNumberEntityDescription(
        key="site_limit",
        translation_key="site_limit",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=1_000_000,
        native_step=1,
        value_fn=lambda export: export.site_limit,
        set_fn=lambda export, value: export.set_site_limit(value),
    ),
    SolarEdgeModbusNumberEntityDescription(
        key="external_production_max",
        translation_key="external_production_max",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=1_000_000,
        native_step=1,
        value_fn=lambda export: export.external_production_max,
        set_fn=lambda export, value: export.set_external_production_max(value),
    ),
)

POWER_NUMBERS: tuple[SolarEdgeModbusNumberEntityDescription[PowerControl], ...] = (
    SolarEdgeModbusNumberEntityDescription(
        key="active_power_limit",
        translation_key="active_power_limit",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=lambda power: power.active_power_limit,
        set_fn=lambda power, value: power.set_active_power_limit(int(value)),
    ),
    SolarEdgeModbusNumberEntityDescription(
        key="cos_phi",
        translation_key="cos_phi",
        entity_category=EntityCategory.CONFIG,
        # Reactive power is grid-code territory, set by the installer or the
        # network operator. Almost nobody should be moving it from Home
        # Assistant, so it has to be asked for.
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
        native_min_value=-1.0,
        native_max_value=1.0,
        native_step=0.01,
        value_fn=lambda power: power.cos_phi,
        set_fn=lambda power, value: power.set_cos_phi(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SolarEdge Modbus number entities based on a config entry."""
    solaredge = entry.runtime_data.solaredge

    entities: list[NumberEntity] = []
    # The storage control block answers on inverters without storage too; the
    # settings only mean something when a battery is actually attached.
    if (storage := solaredge.storage_control) is not None and solaredge.batteries:
        entities.extend(
            SolarEdgeModbusNumberEntity(
                entry=entry, description=description, component=storage
            )
            for description in STORAGE_NUMBERS
        )
    if (export := solaredge.export_control) is not None:
        entities.extend(
            SolarEdgeModbusNumberEntity(
                entry=entry, description=description, component=export
            )
            for description in EXPORT_NUMBERS
        )
    if (power := solaredge.power_control) is not None:
        entities.extend(
            SolarEdgeModbusNumberEntity(
                entry=entry, description=description, component=power
            )
            for description in POWER_NUMBERS
        )

    async_add_entities(entities)


class SolarEdgeModbusNumberEntity[ComponentT: ControlComponent](
    SolarEdgeModbusControlEntity[ComponentT], NumberEntity
):
    """Defines a SolarEdge Modbus number entity."""

    entity_description: SolarEdgeModbusNumberEntityDescription[ComponentT]

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._component)

    @solaredge_exception_handler
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.entity_description.set_fn(self._component, value)
