"""The venstar component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VenstarDataUpdateCoordinator


class VenstarEntity(CoordinatorEntity[VenstarDataUpdateCoordinator]):
    """Representation of a Venstar entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        venstar_data_coordinator: VenstarDataUpdateCoordinator,
        config: ConfigEntry,
    ) -> None:
        """Initialize the data object."""
        super().__init__(venstar_data_coordinator)
        self._config = config
        self._client = venstar_data_coordinator.client

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for this entity."""
        firmware_version = self._client.get_firmware_ver()
        return DeviceInfo(
            identifiers={(DOMAIN, self._config.entry_id)},
            name=self._client.name,
            manufacturer="Venstar",
            model=f"{self._client.model}-{self._client.get_type()}",
            sw_version=f"{firmware_version[0]}.{firmware_version[1]}",
        )
