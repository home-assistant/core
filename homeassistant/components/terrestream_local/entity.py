"""Common stable device identity."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TerrestreamCoordinator as Coordinator


class Entity(CoordinatorEntity[Coordinator]):
    """Represent a sensor with a stable hardware identity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Coordinator, key: str) -> None:
        """Bind a measurement key to the sensor identity."""
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.client.credentials.uuid}_{key}"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return hardware identity and firmware version."""
        d = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.client.credentials.uuid)},
            manufacturer="Terrestream",
            model=d["model"],
            sw_version=d["firmware"],
            hw_version=d.get("hardware"),
            name="Terrestream Indoor Air Quality sensor",
        )
