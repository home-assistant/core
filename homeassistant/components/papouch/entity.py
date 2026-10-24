"""Base class for Papouch entities."""

from aiopapouch import PapouchDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PapouchBaseCoordinator


class PapouchEntity(CoordinatorEntity[PapouchBaseCoordinator]):
    """Common class for all Papouch entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: PapouchBaseCoordinator, device: PapouchDevice
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)

        self.device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.conf.identifier)},
        )
