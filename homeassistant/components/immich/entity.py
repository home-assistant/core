"""Base entity for the Immich integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ImmichDataUpdateCoordinator


class ImmichEntity(CoordinatorEntity[ImmichDataUpdateCoordinator]):
    """Define immich base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ImmichDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="Immich",
            sw_version=coordinator.data.server_about.version,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.configuration_url,
        )
