"""Base DirecTV Entity."""
from __future__ import annotations

from directv import DIRECTV

from homeassistant.const import ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    ATTR_VIA_DEVICE,
    DOMAIN,
)


class DIRECTVEntity(Entity):
    """Defines a base DirecTV entity."""

    def __init__(self, *, dtv: DIRECTV, address: str = "0") -> None:
        """Initialize the DirecTV entity."""
        self._address = address
        self._device_id = address if address != "0" else dtv.device.info.receiver_id
        self._is_client = address != "0"
        self.dtv = dtv

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this DirecTV receiver."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: self.name,
            ATTR_MANUFACTURER: self.dtv.device.info.brand,
            ATTR_MODEL: None,
            ATTR_SOFTWARE_VERSION: self.dtv.device.info.version,
            ATTR_VIA_DEVICE: (DOMAIN, self.dtv.device.info.receiver_id),
        }
