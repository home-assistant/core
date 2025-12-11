from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ConnectSenseCoordinator
from .models import ConnectSenseConfigEntry


class ConnectSenseEntity(CoordinatorEntity[ConnectSenseCoordinator]):
    """Base class for ConnectSense entities."""

    _attr_has_entity_name = True

    def __init__(self, hass, coordinator: ConnectSenseCoordinator, entry: ConnectSenseConfigEntry) -> None:
        super().__init__(coordinator)
        self.hass = hass
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        host = self.entry.data[CONF_HOST]
        uid = self.entry.unique_id or host
        return DeviceInfo(
            identifiers={(DOMAIN, uid)},
            name=self.entry.title or f"Rebooter Pro {uid}",
            manufacturer="Grid Connect",
            model="Rebooter Pro",
        )