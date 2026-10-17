"""Base entity for aerosmart.

One HA device represents the whole installation (both Modbus units); this
integration does not split ventilation/heat-pump into separate devices.
"""

from typing import Any, cast, override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AerosmartCoordinator


class AerosmartEntity(CoordinatorEntity[AerosmartCoordinator]):
    """Common identity, device-info and register access for aerosmart entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AerosmartCoordinator, entity_description: EntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        entry = coordinator.config_entry
        assert entry is not None
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="aerosmart",
        )

    @property
    def _subsystem(self) -> Any:
        """The device-library sub-system object this entity reads/writes.

        Typed ``Any``: ``aerosmart_modbus`` doesn't expose a common base type
        for its per-subsystem component classes to attribute-check against.
        """
        description = cast(Any, self.entity_description)
        return getattr(self.coordinator.device, description.component)

    @property
    @override
    def available(self) -> bool:
        """Return whether this entity's own subsystem refreshed."""
        description = cast(Any, self.entity_description)
        return (
            super().available
            and self.coordinator.data is not None
            and description.component in self.coordinator.data.updated
        )
