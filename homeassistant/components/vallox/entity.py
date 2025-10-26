"""Support for Vallox ventilation units."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import ValloxDataUpdateCoordinator


class ValloxEntity(CoordinatorEntity[ValloxDataUpdateCoordinator]):
    """Representation of a Vallox entity."""

    _attr_has_entity_name = True

    def __init__(self, name: str, coordinator: ValloxDataUpdateCoordinator) -> None:
        """Initialize a Vallox entity."""
        super().__init__(coordinator)

        self._device_uuid = self.coordinator.data.uuid
        assert self.coordinator.config_entry is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._device_uuid))},
            manufacturer=DEFAULT_NAME,
            model=self.coordinator.data.model,
            name=name,
            sw_version=self.coordinator.data.sw_version,
            configuration_url=f"http://{self.coordinator.config_entry.data[CONF_HOST]}",
        )
