"""Base entity for all Mertik Maxitrol fireplace entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MertikDataCoordinator


class MertikEntity(CoordinatorEntity[MertikDataCoordinator]):
    """Shared base: coordinator binding, device info, and has_entity_name."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MertikDataCoordinator, entry_id: str, device_name: str
    ) -> None:
        super().__init__(coordinator)
        self._dataservice: MertikDataCoordinator = coordinator
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=device_name,
            manufacturer="Mertik Maxitrol",
        )
