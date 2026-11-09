"""Base entity for E3/DC devices."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PartKind
from .coordinator import E3dcDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class E3dcPart:
    """A power meter or inverter of the power station, with its own device."""

    kind: PartKind
    slot: int  # E3/DC counts the slots from 0
    numbered: bool  # False while the power station has only one part of this kind

    @property
    def number(self) -> int:
        """The part's number, counted from 1."""
        return self.slot + 1

    @property
    def built_in(self) -> bool:
        """Whether this is the power station's own inverter."""
        return self.kind is PartKind.INVERTER and self.slot == 0


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
            self._attr_device_info = part_device_info(coordinator, part)
        self._attr_unique_id = f"{prefix}_{entity_description.key}"


def part_device_info(
    coordinator: E3dcDataUpdateCoordinator, part: E3dcPart
) -> DeviceInfo | ChildDeviceInfo:
    """Describe the device of a part.

    The power station's own inverter is a child of the power station device, every
    other part is a device connected through it.
    """
    identifier = f"{coordinator.config_entry.unique_id}_{part.kind}_{part.number}"
    if part.numbered:
        translation_key = f"numbered_{part.kind}"
        placeholders: dict[str, str] | None = {"number": str(part.number)}
    else:
        translation_key = part.kind
        placeholders = None
    if part.built_in:
        return ChildDeviceInfo(
            identifiers={(DOMAIN, identifier)},
            parent_device_id=coordinator.station_device_id,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )
    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        translation_key=translation_key,
        translation_placeholders=placeholders,
        via_device_id=coordinator.station_device_id,
    )
