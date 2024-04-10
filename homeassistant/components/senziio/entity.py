"""Senziio base entity."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER


class SenziioEntity(Entity):
    """Representation of a Senziio entity."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize base entity."""
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.data["unique_id"])},
            name=self.entry.title,
            manufacturer=MANUFACTURER,
            model=self.entry.data["model"],
            sw_version=self.entry.data["fw-version"],
            serial_number=self.entry.data["serial-number"],
            connections={(dr.CONNECTION_NETWORK_MAC, self.entry.data["mac-address"])},
        )
