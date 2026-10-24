"""Shared entity identity for one Koito server."""

from typing import TYPE_CHECKING

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import KoitoConfigEntry, KoitoCoordinator


class KoitoEntity(CoordinatorEntity["KoitoCoordinator"]):
    """An entity belonging to a configured Koito service."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KoitoCoordinator, entry: KoitoConfigEntry) -> None:
        """Initialize the shared service identity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Koito",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data[CONF_URL],
        )
