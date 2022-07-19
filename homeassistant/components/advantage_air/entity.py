"""Advantage Air parent entity class."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class AdvantageAirEntity(CoordinatorEntity):
    """Parent class for Advantage Air Entities."""

    _attr_has_entity_name = True

    def __init__(self, instance, ac_key, zone_key=None):
        """Initialize common aspects of an Advantage Air sensor."""
        super().__init__(instance["coordinator"])
        self.async_change = instance["async_change"]
        self.ac_key = ac_key
        self.zone_key = zone_key
        self._attr_unique_id = f'{self.coordinator.data["system"]["rid"]}-{ac_key}'

        self._attr_device_info = DeviceInfo(
            via_device=(DOMAIN, self.coordinator.data["system"]["rid"]),
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Advantage Air",
            model=self.coordinator.data["system"]["sysType"],
            name=self._ac["name"],
        )
        if zone_key:
            self._attr_unique_id += f"-{zone_key}"

    @property
    def _ac(self):
        return self.coordinator.data["aircons"][self.ac_key]["info"]

    @property
    def _zone(self):
        return self.coordinator.data["aircons"][self.ac_key]["zones"][self.zone_key]
