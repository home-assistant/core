"""Support for SolarEdge Modbus switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from solaredged import ExportControl

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SolarEdgeModbusConfigEntry
from .entity import SolarEdgeModbusControlEntity
from .helpers import solaredge_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SolarEdgeModbusSwitchEntityDescription(SwitchEntityDescription):
    """Describes a SolarEdge Modbus switch entity."""

    is_on_fn: Callable[[ExportControl], bool | None]
    set_fn: Callable[[ExportControl, bool], Awaitable[Any]]


EXPORT_SWITCHES: tuple[SolarEdgeModbusSwitchEntityDescription, ...] = (
    SolarEdgeModbusSwitchEntityDescription(
        key="external_production",
        translation_key="external_production",
        entity_category=EntityCategory.CONFIG,
        # An export-control flag the installer sets, and which needs a meter
        # configuration this integration cannot see, so it has to be asked for.
        entity_registry_enabled_default=False,
        is_on_fn=lambda export: export.external_production,
        set_fn=lambda export, enabled: export.set_external_production(enabled=enabled),
    ),
    SolarEdgeModbusSwitchEntityDescription(
        key="negative_site_limit",
        translation_key="negative_site_limit",
        entity_category=EntityCategory.CONFIG,
        # An export-control flag the installer sets, and which needs a meter
        # configuration this integration cannot see, so it has to be asked for.
        entity_registry_enabled_default=False,
        is_on_fn=lambda export: export.negative_site_limit,
        set_fn=lambda export, enabled: export.set_negative_site_limit(enabled=enabled),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeModbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SolarEdge Modbus switch entities based on a config entry."""
    if (export := entry.runtime_data.solaredge.export_control) is None:
        return

    async_add_entities(
        SolarEdgeModbusSwitchEntity(
            entry=entry, description=description, component=export
        )
        for description in EXPORT_SWITCHES
    )


class SolarEdgeModbusSwitchEntity(
    SolarEdgeModbusControlEntity[ExportControl], SwitchEntity
):
    """Defines a SolarEdge Modbus switch entity."""

    entity_description: SolarEdgeModbusSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self._component)

    @solaredge_exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.set_fn(self._component, True)

    @solaredge_exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_fn(self._component, False)
