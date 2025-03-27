"""Base entity for the Pterodactyl integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PterodactylData
from .const import DOMAIN
from .coordinator import PterodactylCoordinator

MANUFACTURER = "Pterodactyl"


class PterodactylEntity(CoordinatorEntity[PterodactylCoordinator]):
    """Representation of a Pterodactyl base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PterodactylCoordinator,
        identifier: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)

        self.identifier = identifier
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=MANUFACTURER,
            name=self.game_server_data.name,
            model=self.game_server_data.name,
            model_id=self.game_server_data.uuid,
            configuration_url=f"{config_entry.data[CONF_URL]}/server/{identifier}",
        )

    @property
    def available(self) -> bool:
        """Return binary sensor availability."""
        return super().available and self.identifier in self.coordinator.data

    @property
    def game_server_data(self) -> PterodactylData:
        """Return game server data."""
        return self.coordinator.data[self.identifier]
