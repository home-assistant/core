"""Base entity for Azure DevOps."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AzureDevOpsDataUpdateCoordinator


class AzureDevOpsEntity(CoordinatorEntity[AzureDevOpsDataUpdateCoordinator]):
    """Defines a base Azure DevOps entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AzureDevOpsDataUpdateCoordinator,
    ) -> None:
        """Initialize the Azure DevOps entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, coordinator.data.organization, coordinator.data.project.name)  # type: ignore[arg-type]
            },
            manufacturer=coordinator.data.organization,
            name=coordinator.data.project.name,
        )
