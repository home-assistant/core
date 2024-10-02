"""Base class for ezbeq entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EzBEQCoordinator


class EzBEQEntity(CoordinatorEntity[EzBEQCoordinator]):
    """Defines a base ezbeq entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EzBEQCoordinator, device_name: str) -> None:
        """Initialize ezbeq entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, f"{coordinator.config_entry.entry_id}_{device_name}")
            },
            name=device_name,
            # in future, can expose model and manufacturer via library (minidsp, qsys, etc)
            via_device=(
                DOMAIN,
                f"{coordinator.config_entry.entry_id}_{DOMAIN}",
            ),
        )
