"""Base entity for the Profalux Neosol integration."""

from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NeosolCoordinator


class NeosolEntity(CoordinatorEntity[NeosolCoordinator]):
    """Base entity for a shutter driven through one dongle channel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: NeosolCoordinator, channel: int) -> None:
        """Initialize the entity bound to ``channel``."""
        super().__init__(coordinator)
        self.channel = channel

        dongle_serial = coordinator.info.serial_number
        self._attr_unique_id = f"{dongle_serial}_{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=MANUFACTURER,
            translation_key="shutter",
            translation_placeholders={"channel": str(channel)},
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, dongle_serial),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the dongle answers and still exposes this channel."""
        return super().available and self.channel in self.coordinator.data
