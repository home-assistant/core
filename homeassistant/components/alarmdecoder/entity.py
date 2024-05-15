"""Support for AlarmDecoder-based alarm control panels entity."""
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
)

class AlarmDecoderEntity(Entity):
    """Define a base AlarmDecoder entity."""

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._client.serial_number)},
            "manufacturer": "NuTech",
            "serial_number": self._client.serial_number,
            "sw_version": self._client.version_number,
        }
