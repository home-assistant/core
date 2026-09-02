"""Common entity for the Persang Infrared integration."""

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class PersangIrEntity(InfraredEmitterConsumerEntity):
    """Persang IR base entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize Persang IR entity."""
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Persang speaker",
            manufacturer="Persang",
        )
