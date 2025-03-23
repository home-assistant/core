"""Base entity for the Pterodactyl integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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

        index = coordinator.api.get_index_from_identifier(identifier)

        if index is None:
            raise HomeAssistantError(
                f"Identifier '{identifier}' not found in data list"
            )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=MANUFACTURER,
            name=coordinator.data[index].name,
            model=coordinator.data[index].name,
            model_id=coordinator.data[index].uuid,
            configuration_url=f"{config_entry.data['host']}/server/{identifier}",
        )
