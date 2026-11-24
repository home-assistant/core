"""Common entity for BenQ Projector Infrared integration."""

from infrared_protocols.codes.benq.projector import BenQProjectorCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_INFRARED_ENTITY_ID, DEVICE_NAME, DOMAIN


class BenQProjectorIrEntity(InfraredEmitterConsumerEntity):
    """BenQ Projector Infrared base entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str) -> None:
        """Initialize BenQ Projector Infrared entity."""
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAME,
            manufacturer="BenQ",
        )

    async def _send_benq_command(self, code: BenQProjectorCode) -> None:
        """Send an IR command to the BenQ projector."""
        await self._send_command(code.to_command())
