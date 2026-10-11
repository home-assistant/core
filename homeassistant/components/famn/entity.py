"""Base entity for the Famn integration."""

from typing import TYPE_CHECKING, override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_URL, DOMAIN
from .coordinator import FamnChoresCoordinator, FamnConfigEntry


def famn_device_info(config_entry: FamnConfigEntry) -> DeviceInfo:
    """Return the service device shared by all entities of the entry."""
    unique_id = config_entry.unique_id
    if TYPE_CHECKING:
        assert unique_id is not None
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, unique_id)},
        manufacturer="Famn",
        name=config_entry.title,
        configuration_url=BASE_URL,
    )


class FamnEntity(CoordinatorEntity[FamnChoresCoordinator]):
    """Defines a base Famn entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FamnChoresCoordinator, key: str) -> None:
        """Initialize the Famn entity."""
        super().__init__(coordinator)

        unique_id = coordinator.config_entry.unique_id
        if TYPE_CHECKING:
            assert unique_id is not None

        self._key = key
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_device_info = famn_device_info(coordinator.config_entry)

    @property
    @override
    def available(self) -> bool:
        """Return if the underlying Famn object still exists."""
        return super().available and self._key in self.coordinator.data
