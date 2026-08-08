"""Common entity for Marantz IR integration."""

from infrared_protocols.codes.marantz import models as marantz_models
from infrared_protocols.codes.marantz.audio import MarantzAudioCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.const import CONF_MODEL
from homeassistant.helpers.device_registry import DeviceInfo

from . import MarantzIrConfigEntry
from .const import DOMAIN, MODELS


class MarantzIrEntity(InfraredEmitterConsumerEntity):
    """Marantz IR base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MarantzIrConfigEntry,
        infrared_entity_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize Marantz IR entity."""
        self._infrared_emitter_entity_id = infrared_entity_id
        self._runtime_data = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        lib_model = MODELS[entry.data[CONF_MODEL]]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Marantz {lib_model.name}",
            manufacturer="Marantz",
            model=None if lib_model is marantz_models.GENERIC else lib_model.name,
        )

    async def _send_marantz_command(
        self, code: MarantzAudioCode, repeat_count: int = 0
    ) -> None:
        """Send an IR command using the Marantz protocol.

        Flips the RC-5 toggle bit before each frame so the receiver
        treats consecutive presses as new presses, not as a held repeat.
        """
        self._runtime_data.toggle ^= 1
        await self._send_command(
            code.to_command(repeat_count=repeat_count, toggle=self._runtime_data.toggle)
        )
