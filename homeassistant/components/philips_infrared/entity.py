"""Common entity for Philips IR integration."""

from infrared_protocols.codes.philips.tv import PhilipsTVCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.helpers.device_registry import DeviceInfo

from . import PhilipsIrConfigEntry
from .const import DOMAIN


class PhilipsIrEntity(InfraredEmitterConsumerEntity):
    """Philips IR base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PhilipsIrConfigEntry,
        infrared_entity_id: str,
        unique_id_suffix: str | None = None,
    ) -> None:
        """Initialize Philips IR entity."""
        self._infrared_emitter_entity_id = infrared_entity_id
        self._runtime_data = entry.runtime_data
        self._attr_unique_id = (
            entry.entry_id
            if unique_id_suffix is None
            else f"{entry.entry_id}_{unique_id_suffix}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Philips TV",
            manufacturer="Philips",
        )

    async def _send_philips_command(self, code: PhilipsTVCode) -> None:
        """Send an IR command, flipping the RC-6 toggle bit first."""
        self._runtime_data.toggle ^= 1
        await self._send_command(code.to_command(toggle=self._runtime_data.toggle))
