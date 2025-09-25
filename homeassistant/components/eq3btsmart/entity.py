"""Base class for all eQ-3 entities."""

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import Eq3ConfigEntry
from .const import CONF_MAC_ADDRESS, DEVICE_MODEL, MANUFACTURER
from .coordinator import Eq3Coordinator


class Eq3Entity(CoordinatorEntity[Eq3Coordinator]):
    """Base class for all eQ-3 entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: Eq3ConfigEntry,
        unique_id_key: str | None = None,
    ) -> None:
        """Initialize the eq3 entity."""
        super().__init__(entry.runtime_data.coordinator)
        self._thermostat = entry.runtime_data.thermostat
        self._mac_address = entry.data[CONF_MAC_ADDRESS]
        self._attr_device_info = DeviceInfo(
            name=slugify(self._mac_address),
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            connections={(CONNECTION_BLUETOOTH, self._mac_address)},
        )
        suffix = f"_{unique_id_key}" if unique_id_key else ""
        self._attr_unique_id = f"{format_mac(self._mac_address)}{suffix}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_available = self.coordinator.last_update_success
        super()._handle_coordinator_update()
