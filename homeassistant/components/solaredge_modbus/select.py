"""Support for SolarEdge Modbus select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from solaredged import (
    ExportControl,
    ExportControlLimit,
    ExportControlMode,
    SolarEdge,
    StorageChargePolicy,
    StorageControl,
    StorageControlMode,
    StorageMode,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SolarEdgeModbusConfigEntry
from .entity import ControlComponent, SolarEdgeModbusControlEntity
from .helpers import solaredge_exception_handler

PARALLEL_UPDATES = 1

# Export limiting has no dedicated "off" enum member; the library models a
# disabled limiter as mode None, exposed here as an explicit option.
EXPORT_MODE_DISABLED = "disabled"


@dataclass(frozen=True, kw_only=True)
class SolarEdgeModbusSelectEntityDescription[ComponentT](SelectEntityDescription):
    """Describes a SolarEdge Modbus select entity."""

    current_fn: Callable[[ComponentT], str | None]
    # Options that depend on the detected layout, like meter presence.
    options_fn: Callable[[SolarEdge], list[str]] | None = None
    select_fn: Callable[[ComponentT, str], Awaitable[Any]]


STORAGE_SELECTS: tuple[SolarEdgeModbusSelectEntityDescription[StorageControl], ...] = (
    SolarEdgeModbusSelectEntityDescription(
        key="storage_control_mode",
        translation_key="storage_control_mode",
        entity_category=EntityCategory.CONFIG,
        options=[mode.name.lower() for mode in StorageControlMode],
        current_fn=lambda storage: (
            storage.control_mode.name.lower()
            if storage.control_mode is not None
            else None
        ),
        select_fn=lambda storage, option: storage.set_control_mode(
            StorageControlMode[option.upper()]
        ),
    ),
    SolarEdgeModbusSelectEntityDescription(
        key="storage_ac_charge_policy",
        translation_key="storage_ac_charge_policy",
        entity_category=EntityCategory.CONFIG,
        options=[policy.name.lower() for policy in StorageChargePolicy],
        current_fn=lambda storage: (
            storage.ac_charge_policy.name.lower()
            if storage.ac_charge_policy is not None
            else None
        ),
        select_fn=lambda storage, option: storage.set_ac_charge_policy(
            StorageChargePolicy[option.upper()]
        ),
    ),
    SolarEdgeModbusSelectEntityDescription(
        key="storage_default_mode",
        translation_key="storage_default_mode",
        entity_category=EntityCategory.CONFIG,
        options=[mode.name.lower() for mode in StorageMode],
        current_fn=lambda storage: (
            storage.default_mode.name.lower()
            if storage.default_mode is not None
            else None
        ),
        select_fn=lambda storage, option: storage.set_default_mode(
            StorageMode[option.upper()]
        ),
    ),
    SolarEdgeModbusSelectEntityDescription(
        key="storage_command_mode",
        translation_key="storage_command_mode",
        entity_category=EntityCategory.CONFIG,
        options=[mode.name.lower() for mode in StorageMode],
        current_fn=lambda storage: (
            storage.command_mode.name.lower()
            if storage.command_mode is not None
            else None
        ),
        select_fn=lambda storage, option: storage.set_command_mode(
            StorageMode[option.upper()]
        ),
    ),
)

EXPORT_SELECTS: tuple[SolarEdgeModbusSelectEntityDescription[ExportControl], ...] = (
    SolarEdgeModbusSelectEntityDescription(
        key="export_control_mode",
        translation_key="export_control_mode",
        entity_category=EntityCategory.CONFIG,
        # Limiting export by a meter reading needs a meter to read.
        options_fn=lambda solaredge: [
            EXPORT_MODE_DISABLED,
            *(
                mode.name.lower()
                for mode in ExportControlMode
                if solaredge.meters or mode is ExportControlMode.PRODUCTION_CONTROL
            ),
        ],
        current_fn=lambda export: (
            export.mode.name.lower()
            if export.mode is not None
            else EXPORT_MODE_DISABLED
        ),
        select_fn=lambda export, option: export.set_mode(
            None
            if option == EXPORT_MODE_DISABLED
            else ExportControlMode[option.upper()]
        ),
    ),
    SolarEdgeModbusSelectEntityDescription(
        key="export_control_limit_type",
        translation_key="export_control_limit_type",
        entity_category=EntityCategory.CONFIG,
        # Whether the site limit counts per phase or in total is part of the
        # export-control setup the installer does, not day-to-day operation.
        entity_registry_enabled_default=False,
        options=[limit.name.lower() for limit in ExportControlLimit],
        current_fn=lambda export: (
            export.limit_type.name.lower() if export.limit_type is not None else None
        ),
        select_fn=lambda export, option: export.write(
            "limit_type", ExportControlLimit[option.upper()]
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SolarEdge Modbus select entities based on a config entry."""
    solaredge = entry.runtime_data.solaredge

    entities: list[SelectEntity] = []
    # The storage control block answers on inverters without storage too; the
    # settings only mean something when a battery is actually attached.
    if (storage := solaredge.storage_control) is not None and solaredge.batteries:
        entities.extend(
            SolarEdgeModbusSelectEntity(
                entry=entry, description=description, component=storage
            )
            for description in STORAGE_SELECTS
        )
    if (export := solaredge.export_control) is not None:
        entities.extend(
            SolarEdgeModbusSelectEntity(
                entry=entry, description=description, component=export
            )
            for description in EXPORT_SELECTS
        )

    async_add_entities(entities)


class SolarEdgeModbusSelectEntity[ComponentT: ControlComponent](
    SolarEdgeModbusControlEntity[ComponentT], SelectEntity
):
    """Defines a SolarEdge Modbus select entity."""

    entity_description: SolarEdgeModbusSelectEntityDescription[ComponentT]

    @property
    @override
    def options(self) -> list[str]:
        """Return the options this site can use, plus the one it is set to.

        A mode that needs hardware the site does not have is left out. The
        exception is whatever the inverter is set to right now, which can be
        anything an installer or the SolarEdge app left behind: the register is
        the truth, and an entity may not report a state outside its options.
        """
        description = self.entity_description
        options = (
            description.options_fn(self.coordinator.solaredge)
            if description.options_fn is not None
            else super().options
        )

        current = self.current_option
        if current is not None and current not in options:
            return [*options, current]

        return options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected option."""
        return self.entity_description.current_fn(self._component)

    @solaredge_exception_handler
    @override
    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.entity_description.select_fn(self._component, option)
