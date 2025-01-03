"""Define a base Tile entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TileCoordinator


class TileEntity(CoordinatorEntity[TileCoordinator]):
    """Define a base Tile entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TileCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._tile = coordinator.tile
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._tile.uuid)},
            name=self._tile.name,
            manufacturer="Tile Inc.",
            hw_version=self._tile.hardware_version,
            sw_version=self._tile.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and not self._tile.dead
