"""Shared entity implementation for Karaca Connect."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KaracaConfigEntry
from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import KaracaCoordinator


class KaracaEntity(CoordinatorEntity[KaracaCoordinator]):
    """An entity belonging to a single Karaca Connect device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KaracaCoordinator, entry: KaracaConfigEntry) -> None:
        super().__init__(coordinator)
        device_id = str(entry.data[CONF_DEVICE_ID])
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": entry.title,
            "manufacturer": "Karaca",
        }

    @property
    def available(self) -> bool:
        """Avoid showing a stale reading when the cloud reports disconnection."""
        if not super().available:
            return False
        meta = self.coordinator.data.get("meta")
        return not (isinstance(meta, dict) and meta.get("connected") is False)
