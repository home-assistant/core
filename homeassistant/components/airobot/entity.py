"""Base entity for Airobot integration."""

from __future__ import annotations

from homeassistant.const import CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirobotDataUpdateCoordinator


class AirobotEntity(CoordinatorEntity[AirobotDataUpdateCoordinator]):
    """Base class for Airobot entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        status = coordinator.data.status
        settings = coordinator.data.settings

        self._attr_unique_id = status.device_id

        connections = set()
        if (mac := coordinator.config_entry.data.get(CONF_MAC)) is not None:
            connections.add((CONNECTION_NETWORK_MAC, mac))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, status.device_id)},
            connections=connections,
            name=settings.device_name or status.device_id,
            manufacturer="Airobot",
            model="Thermostat",
            model_id="TE1",
            sw_version=str(status.fw_version),
            hw_version=str(status.hw_version),
        )
