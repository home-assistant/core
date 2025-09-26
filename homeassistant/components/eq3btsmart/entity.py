"""Base class for all eQ-3 entities."""

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DEVICE_MODEL, MANUFACTURER
from .coordinator import Eq3ConfigEntry, Eq3Coordinator


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
        self._thermostat = entry.runtime_data.coordinator.thermostat
        if TYPE_CHECKING:
            assert entry.unique_id is not None
        self._mac_address: str = entry.unique_id
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
