"""Base DirecTV Entity."""

from directv import DIRECTV

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import DirecTVConfigEntry
from .const import DOMAIN


class DIRECTVEntity(Entity):
    """Defines a base DirecTV entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        dtv: DIRECTV,
        entry: DirecTVConfigEntry,
        name: str,
        address: str = "0",
    ) -> None:
        """Initialize the DirecTV entity."""
        self._address = address
        self._device_id = address if address != "0" else dtv.device.info.receiver_id
        self._is_client = address != "0"
        self.dtv = dtv
        via_device_id: str | None = None
        if self._is_client:
            via_device_id = dr.async_get_device_id_by_identifier(
                hass,
                (DOMAIN, dtv.device.info.receiver_id),
                config_entry_id=entry.entry_id,
            )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=dtv.device.info.brand,
            name=name,
            sw_version=dtv.device.info.version,
        )
        if via_device_id is not None:
            self._attr_device_info["via_device_id"] = via_device_id
