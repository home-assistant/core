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
            assert coordinator.config_entry.unique_id is not None
        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{unique_id}_{entity_type}"
        entry_data = coordinator.config_entry.data
        model: str = entry_data[CONF_DEVICE_DESC]
        if entry_data[CONF_DEVICE_TYPE] == DEV_HUB:
            model = f"Hub {entry_data[CONF_HUB_ID]}"
        self._attr_device_info = DeviceInfo(
            manufacturer="Chandler Systems, Inc.",
            model=model,
            name=entry_data[CONF_DEVICE_NAME],
            identifiers={(DOMAIN, unique_id)},
        )
        if entry_data[CONF_DEVICE_TYPE] != DEV_HUB:
            self._attr_device_info.update(
                {
                    "via_device": (
                        DOMAIN,
                        entry_data[CONF_DEVICE_OWNER_ID],
                    )
                }
            )
