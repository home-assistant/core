"""Support for AlarmDecoder-based alarm control panels entity."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class AlarmDecoderEntity(Entity):
    """Define a base AlarmDecoder entity."""

    _attr_has_entity_name = True

    def __init__(self, client):
        """Initialize the alarm decoder entity."""
        self._client = client
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, client.serial_number)},
            manufacturer="NuTech",
            serial_number=client.serial_number,
            sw_version=client.version_number,
        )
