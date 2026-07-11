"""Commonly shared code for the MELCloud Home integration."""

from collections.abc import Callable, Iterable

from aiomelcloudhome import ATAUnit, ATWUnit

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MelCloudHomeCoordinator


@callback
def async_setup_unit_entities(
    coordinator: MelCloudHomeCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    ata_entities_fn: Callable[[list[ATAUnit]], Iterable[Entity]],
    atw_entities_fn: Callable[[list[ATWUnit]], Iterable[Entity]],
) -> None:
    """Add entities for the current units and register callbacks for new units."""

    def _async_add_new_ata_units(units: list[ATAUnit]) -> None:
        async_add_entities(ata_entities_fn(units))

    def _async_add_new_atw_units(units: list[ATWUnit]) -> None:
        async_add_entities(atw_entities_fn(units))

    coordinator.new_ata_callbacks.append(_async_add_new_ata_units)
    coordinator.new_atw_callbacks.append(_async_add_new_atw_units)

    _async_add_new_ata_units(list(coordinator.ata_units.values()))
    _async_add_new_atw_units(list(coordinator.atw_units.values()))


def unit_ids(unit: ATAUnit | ATWUnit) -> dict[str, list[str]]:
    """Return the client keyword argument selecting this unit."""
    if isinstance(unit, ATAUnit):
        return {"ata_unit_ids": [unit.id]}
    return {"atw_unit_ids": [unit.id]}
