"""Base entity for E3/DC devices."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import E3dcDataUpdateCoordinator

# A part of the power station with its own device, as (device translation key, slot)
type E3dcPart = tuple[str, int]


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
            device_info = coordinator.device_info
        else:
            kind, number = part
            prefix = f"{serial}_{kind}_{number}"
            device_info = DeviceInfo(
                identifiers={(DOMAIN, prefix)},
                translation_key=kind,
                translation_placeholders={"number": str(number)},
                via_device_id=coordinator.station_device_id,
            )
        self._attr_unique_id = f"{prefix}_{entity_description.key}"
        self._attr_device_info = device_info
