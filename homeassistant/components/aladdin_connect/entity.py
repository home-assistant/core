"""Defines a base Aladdin Connect entity."""

from genie_partner_sdk.model import GarageDoor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AladdinConnectCoordinator


class AladdinConnectEntity(CoordinatorEntity[AladdinConnectCoordinator]):
    """Defines a base Aladdin Connect entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AladdinConnectCoordinator, device: GarageDoor
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.unique_id)},
            name=device.name,
            manufacturer="Overhead Door",
        )
