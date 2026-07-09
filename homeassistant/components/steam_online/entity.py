"""Entity classes for the Steam integration."""

from typing import override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SteamDataUpdateCoordinator


class SteamEntity(CoordinatorEntity[SteamDataUpdateCoordinator]):
    """Representation of a Steam entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SteamDataUpdateCoordinator,
        steamid: str,
        description: EntityDescription,
    ) -> None:
        """Initialize a Steam entity."""
        super().__init__(coordinator)
        self._steamid = steamid
        self.entity_description = description
        self._attr_unique_id = f"{steamid}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.data[steamid].profileurl,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, steamid)},
            manufacturer=DEFAULT_NAME,
            name=coordinator.data[steamid].personaname,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._steamid in self.coordinator.data
