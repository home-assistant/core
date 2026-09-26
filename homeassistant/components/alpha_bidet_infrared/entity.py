"""Common entity for the Alpha Bidet Infrared integration."""

from infrared_protocols.codes.alpha_bidet.models import AlphaBidetModel

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN


class AlphaBidetIrEntity(InfraredEmitterConsumerEntity):
    """Alpha Bidet IR base entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str) -> None:
        """Initialize Alpha Bidet IR entity."""
        model = AlphaBidetModel(entry.data[CONF_MODEL])
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Alpha Bidet {model.value}",
            manufacturer="Alpha Bidet",
            model=model.value,
        )
