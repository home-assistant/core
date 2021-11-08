"""Advantage Air parent entity class."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class AdvantageAirEntity(CoordinatorEntity):
    """Parent class for Advantage Air Entities."""

    def __init__(self, instance, ac_key, zone_key=None):
        """Initialize common aspects of an Advantage Air sensor."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.ac_key = ac_key
        self.zone_key = zone_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["system"]["rid"])},
            manufacturer="Advantage Air",
            model=self.coordinator.data["system"]["sysType"],
            name=self.coordinator.data["system"]["name"],
            sw_version=self.coordinator.data["system"]["myAppRev"],
        )

    @property
    def _ac(self):
        return self.coordinator.data["aircons"][self.ac_key]["info"]

    @property
    def _zone(self):
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]
