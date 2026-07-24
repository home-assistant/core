"""The NZBGet integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NZBGetDataUpdateCoordinator


class NZBGetEntity(CoordinatorEntity[NZBGetDataUpdateCoordinator]):
    """Defines a base NZBGet entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry_id: str,
        entry_name: str,
        coordinator: NZBGetDataUpdateCoordinator,
    ) -> None:
        """Initialize the NZBGet entity."""
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=entry_name,
            entry_type=DeviceEntryType.SERVICE,
        )
