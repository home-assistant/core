"""Base class for Cambridge Audio entities."""

from aiostreammagic import StreamMagicClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class CambridgeAudioEntity(Entity):
    """Defines a base Cambridge Audio entity."""

    _attr_has_entity_name = True

    def __init__(self, client: StreamMagicClient) -> None:
        """Initialize Cambridge Audio entity."""
        self.client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.info.unit_id)},
            name=client.info.name,
            manufacturer="Cambridge Audio",
            model=client.info.model,
            serial_number=client.info.unit_id,
            configuration_url=f"http://{client.host}",
        )
