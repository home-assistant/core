"""Base entity class for DROP entities."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_DESC,
    CONF_DEVICE_NAME,
    CONF_DEVICE_OWNER_ID,
    CONF_DEVICE_TYPE,
    CONF_HUB_ID,
    DEV_HUB,
    DOMAIN,
)
from .coordinator import DROPDeviceDataUpdateCoordinator


class DROPEntity(CoordinatorEntity[DROPDeviceDataUpdateCoordinator]):
    """Representation of a DROP device entity."""

    _attr_has_entity_name = True

    def __init__(
        self, entity_type: str, coordinator: DROPDeviceDataUpdateCoordinator
    ) -> None:
        """Init DROP entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry is not None
            assert coordinator.config_entry.unique_id is not None
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_type}"
        model: str = coordinator.config_entry.data[CONF_DEVICE_DESC]
        if coordinator.config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
            model = f"Hub {coordinator.config_entry.data[CONF_HUB_ID]}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Chandler Systems, Inc.",
            model=model,
            name=coordinator.config_entry.data[CONF_DEVICE_NAME],
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
        )
        if coordinator.config_entry.data[CONF_DEVICE_TYPE] != DEV_HUB:
            self._attr_device_info.update(
                {
                    "via_device": (
                        DOMAIN,
                        coordinator.config_entry.data[CONF_DEVICE_OWNER_ID],
                    )
                }
            )
