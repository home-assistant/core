"""Common entity for Gree IR integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import GreeIrConfigEntry
from .const import DOMAIN


class GreeIrEntity(Entity):
    """Gree IR base entity providing common device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: GreeIrConfigEntry,
        unique_id_suffix: str | None = None,
        device_name: str = "Gree AC",
    ) -> None:
        """Initialize Gree IR entity."""
        self._runtime_data = entry.runtime_data
        self._attr_unique_id = (
            entry.entry_id
            if unique_id_suffix is None
            else f"{entry.entry_id}_{unique_id_suffix}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Gree",
        )
