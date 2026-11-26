"""Base entity for E3/DC devices."""

from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PartKind
from .coordinator import E3dcConfigEntry, E3dcDataUpdateCoordinator, E3dcPart


class E3dcEntity(CoordinatorEntity[E3dcDataUpdateCoordinator]):
    """Defines a base E3/DC entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: E3dcDataUpdateCoordinator,
        entity_description: EntityDescription,
        part: E3dcPart | None = None,
    ) -> None:
        """Initialize the entity, on the power station or on one of its parts."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        serial = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert serial is not None
        if part is None:
            prefix = serial
            self._attr_device_info = coordinator.device_info
        else:
            prefix = f"{serial}_{part.kind}_{part.number}"
            self._attr_device_info = _part_device_info(coordinator, part, prefix)
        self._attr_unique_id = f"{prefix}_{entity_description.key}"


class E3dcPartEntity(E3dcEntity):
    """Defines an entity of a power meter or an inverter."""

    def __init__(
        self,
        coordinator: E3dcDataUpdateCoordinator,
        entity_description: EntityDescription,
        part: E3dcPart,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description, part)
        self._part = part

    @property
    @override
    def available(self) -> bool:
        return super().available and self._part in self.coordinator.parts


@callback
def async_add_part_entities[_DescriptionT: EntityDescription](
    entry: E3dcConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    descriptions: Mapping[PartKind, Iterable[_DescriptionT]],
    entity_factory: Callable[
        [E3dcDataUpdateCoordinator, _DescriptionT, E3dcPart], Entity
    ],
) -> None:
    """Add a platform's entities for each part the first time the power station reports it."""
    coordinator = entry.runtime_data
    added: set[E3dcPart] = set()

    @callback
    def _async_add_new() -> None:
        new = sorted(
            part for part in coordinator.parts - added if part.kind in descriptions
        )
        added.update(new)
        entities = [
            entity_factory(coordinator, description, part)
            for part in new
            for description in descriptions[part.kind]
        ]
        if entities:
            async_add_entities(entities)

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


def _part_device_info(
    coordinator: E3dcDataUpdateCoordinator, part: E3dcPart, identifier: str
) -> DeviceInfo | ChildDeviceInfo:
    """Describe the device of a part.

    The power station's own inverter is a child of the power station device, every
    other part is a device connected through it.
    """
    placeholders = {"number": str(part.number)}
    if part.built_in:
        return ChildDeviceInfo(
            identifiers={(DOMAIN, identifier)},
            parent_device_id=coordinator.station_device_id,
            translation_key=part.kind,
            translation_placeholders=placeholders,
        )
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        translation_key=part.kind,
        translation_placeholders=placeholders,
        via_device_id=coordinator.station_device_id,
    )
