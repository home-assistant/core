"""The Tautulli integration."""

from __future__ import annotations

from pytautulli import PyTautulliApiUser

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import TautulliDataUpdateCoordinator


class TautulliEntity(CoordinatorEntity[TautulliDataUpdateCoordinator]):
    """Defines a base Tautulli entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TautulliDataUpdateCoordinator,
        description: EntityDescription,
        user: PyTautulliApiUser | None = None,
    ) -> None:
        """Initialize the Tautulli entity."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description
        self.user = user
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.host_configuration.base_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, user.user_id if user else entry_id)},
            manufacturer=DEFAULT_NAME,
            name=user.username if user else DEFAULT_NAME,
        )
