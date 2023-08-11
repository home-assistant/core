"""Base DirecTV Entity."""
from __future__ import annotations

from typing import cast

from directv import DIRECTV

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


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
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=self.dtv.device.info.brand,
            # Instead of setting the device name to the entity name, directv
            # should be updated to set has_entity_name = True, and set the entity
            # name to None
            name=cast(str | None, self.name),
            sw_version=self.dtv.device.info.version,
            via_device=(DOMAIN, self.dtv.device.info.receiver_id),
        )
