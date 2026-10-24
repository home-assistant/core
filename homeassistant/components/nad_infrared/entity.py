"""Common entity for NAD Infrared integration."""

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .codes import NADAmplifierCode, NADCassetteCode, NADCDCode
from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, DEVICE_NAMES, DOMAIN


class NadIrEntity(InfraredEmitterConsumerEntity):
    """NAD Infrared base entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique_id_suffix: str) -> None:
        """Initialize NAD Infrared entity."""
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
        self._attr_unique_id = f"{entry.entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEVICE_NAMES[entry.data[CONF_DEVICE_TYPE]],
            manufacturer="NAD",
        )

    async def _send_nad_command(
        self, code: NADAmplifierCode | NADCDCode | NADCassetteCode
    ) -> None:
        """Send an IR command to the NAD device."""
        await self._send_command(code.to_command())
