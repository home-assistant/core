"""Base class for Mastodon entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MastodonCoordinator


class MastodonEntity(CoordinatorEntity[MastodonCoordinator]):
    """Defines a base Mastodon entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MastodonCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize Mastodon entity."""
        super().__init__(coordinator)
        unique_id = coordinator.config_entry.unique_id
        assert unique_id is not None
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
        )
        self.entity_description = description
