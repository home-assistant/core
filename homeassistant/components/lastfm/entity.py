"""Base entity for the Last.fm integration."""

import hashlib
from typing import override

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import LastFMDataUpdateCoordinator, LastFMUserData


class LastFmEntity(CoordinatorEntity[LastFMDataUpdateCoordinator]):
    """Base class for Last.fm user entities."""

    _attr_attribution = "Data provided by Last.fm"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LastFMDataUpdateCoordinator,
        username: str,
        entry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._username = username
        self._user_hash = hashlib.sha256(username.encode("utf-8")).hexdigest()
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.last.fm",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{entry_id}_{self._user_hash}")},
            manufacturer=DEFAULT_NAME,
            name=f"{DEFAULT_NAME} {username}",
        )

    @property
    def user_data(self) -> LastFMUserData | None:
        """Returns the user from the coordinator."""
        return self.coordinator.data.get(self._username)

    @property
    @override
    def available(self) -> bool:
        """If user not found in coordinator, entity is unavailable."""
        return super().available and self.user_data is not None
