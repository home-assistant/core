"""Base class for Palazzetti entities."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import PALAZZETTI
from .coordinator import PalazzettiDataUpdateCoordinator


class PalazzettiEntity(CoordinatorEntity[PalazzettiDataUpdateCoordinator]):
    """Defines a base Palazzetti entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PalazzettiDataUpdateCoordinator) -> None:
        """Initialize Palazzetti entity."""
        super().__init__(coordinator)
        client = coordinator.client
        mac = coordinator.config_entry.unique_id
        assert mac is not None
        self._attr_device_info = dr.DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=client.name,
            manufacturer=PALAZZETTI,
            sw_version=client.sw_version,
            hw_version=client.hw_version,
        )

    @property
    def available(self) -> bool:
        """Is the entity available."""
        return super().available and self.coordinator.client.connected
