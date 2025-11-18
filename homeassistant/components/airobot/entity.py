"""Base entity for Airobot integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirobotDataUpdateCoordinator


class AirobotEntity(CoordinatorEntity[AirobotDataUpdateCoordinator]):
    """Base class for Airobot entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
        entity_key: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        status = coordinator.data.status
        settings = coordinator.data.settings

        if entity_key:
            self._attr_unique_id = f"{status.device_id}_{entity_key}"
        else:
            self._attr_unique_id = status.device_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, status.device_id)},
            name=settings.device_name or status.device_id,
            manufacturer="Airobot",
            model="Thermostat",
            model_id="TE1",
            sw_version=str(status.fw_version),
            hw_version=str(status.hw_version),
        )
