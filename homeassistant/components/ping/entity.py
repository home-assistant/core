"""Base entity for Ping integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PingUpdateCoordinator


class BasePingEntity(CoordinatorEntity[PingUpdateCoordinator]):
    """Representation of a Ping base entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, config_entry: ConfigEntry, coordinator: PingUpdateCoordinator
    ) -> None:
        """Initialize the Ping Binary sensor."""
        super().__init__(coordinator)

        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.ip_address)},
            manufacturer="Ping",
        )

        self.config_entry = config_entry
