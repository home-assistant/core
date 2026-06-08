"""Common entities for the OSRAM IR integration."""

from asyncio import sleep

from infrared_protocols.codes.osram.light import OsramLightCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

FULL_FRAME_REPEAT_DELAY = 0.01


class OsramIrEntity(Entity):
    """OSRAM IR base entity providing common device information."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str) -> None:
        """Initialize an OSRAM IR entity."""
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="OSRAM light",
            manufacturer="OSRAM",
        )


class OsramIrEmitterEntity(OsramIrEntity, InfraredEmitterConsumerEntity):
    """Base entity that sends commands through an infrared emitter."""

    def __init__(
        self,
        entry: ConfigEntry,
        infrared_entity_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize an OSRAM IR emitter consumer entity."""
        super().__init__(entry, unique_id_suffix)
        self._infrared_emitter_entity_id = infrared_entity_id

    async def _async_send_code(
        self,
        code: OsramLightCode,
        *,
        full_frame_count: int = 1,
    ) -> None:
        """Send an OSRAM command one or more times as complete NEC frames."""
        for frame_index in range(full_frame_count):
            if frame_index:
                await sleep(FULL_FRAME_REPEAT_DELAY)

            await self._send_command(code.to_command())
