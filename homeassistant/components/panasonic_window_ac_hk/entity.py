"""Base entity for the Panasonic Window A/C (Hong Kong/Macau) integration."""

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.helpers.device_registry import DeviceInfo

from . import PanasonicWindowAcHKConfigEntry
from .command import PanasonicWindowAcHKCommand
from .const import DOMAIN


class PanasonicWindowAcHKEntity(InfraredEmitterConsumerEntity):
    """Base entity sharing one air conditioner's assumed state and emitter."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: PanasonicWindowAcHKConfigEntry, unique_id_suffix: str
    ) -> None:
        """Initialize the entity from a config entry."""
        self._runtime_data = entry.runtime_data
        self._infrared_emitter_entity_id = entry.runtime_data.infrared_emitter_entity_id
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Panasonic",
            model="Window-Type A/C (CW-HU/HZ/SU/SUL, Hong Kong/Macau)",
        )

    async def _async_send_full(self) -> None:
        """Send the current full state frame through the infrared emitter."""
        data = self._runtime_data
        await self._send_command(
            PanasonicWindowAcHKCommand.full(
                off=not data.power,
                mode=data.mode,
                temp=data.temp,
                fan=data.fan,
                swing=data.swing,
                nanoex=data.nanoex,
            )
        )

    async def _async_send_short(self, kind: str) -> None:
        """Send a Quiet/Powerful short toggle frame."""
        await self._send_command(PanasonicWindowAcHKCommand.short(kind))
