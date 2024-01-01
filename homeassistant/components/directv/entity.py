"""Base DirecTV Entity."""
from __future__ import annotations

from directv import DIRECTV

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class DIRECTVEntity(Entity):
    """Defines a base DirecTV entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, *, dtv: DIRECTV, name: str, address: str = "0") -> None:
        """Initialize the DirecTV entity."""
        self._address = address
        self._device_id = address if address != "0" else dtv.device.info.receiver_id
        self._is_client = address != "0"
        self.dtv = dtv
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=self.dtv.device.info.brand,
            name=name,
            sw_version=self.dtv.device.info.version,
            via_device=(DOMAIN, self.dtv.device.info.receiver_id),
        )
