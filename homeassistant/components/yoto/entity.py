"""Base entity for the Yoto integration."""

from yoto_api import YotoPlayer

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import YotoDataUpdateCoordinator


class YotoEntity(CoordinatorEntity[YotoDataUpdateCoordinator]):
    """Base class for Yoto entities tied to a single player."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._player_id = player.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, player.id)},
            connections={(CONNECTION_NETWORK_MAC, player.mac)} if player.mac else set(),
            manufacturer=MANUFACTURER,
            model=player.model,
            model_id=player.device_type,
            hw_version=player.generation,
            name=player.name,
            sw_version=player.firmware_version,
        )

    @property
    def player(self) -> YotoPlayer:
        """Return the live player record from the coordinator."""
        return self.coordinator.data[self._player_id]

    @property
    def available(self) -> bool:
        """Return True if the player is still tracked by the coordinator."""
        return super().available and self._player_id in self.coordinator.data
