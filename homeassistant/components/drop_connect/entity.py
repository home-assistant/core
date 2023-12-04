"""Base entity class for DROP entities."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_TYPE, CONF_HUB_ID, DEV_HUB, DOMAIN
from .coordinator import DROPDeviceDataUpdateCoordinator


class DROPEntity(CoordinatorEntity[DROPDeviceDataUpdateCoordinator]):
    """Representation of a DROP device entity."""

    _attr_force_update = False
    _attr_has_entity_name = True
    _attr_should_poll = False

    coordinator: DROPDeviceDataUpdateCoordinator

    def __init__(
        self, entity_type: str, coordinator: DROPDeviceDataUpdateCoordinator
    ) -> None:
        """Init DROP entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{entity_type}"
        self._attr_device_info = DeviceInfo(
            manufacturer=coordinator.manufacturer,
            model=coordinator.model,
            name=coordinator.device_name,
        )
        if coordinator.config_entry.data[CONF_DEVICE_TYPE] == DEV_HUB:
            self._attr_device_info.update(
                {"identifiers": {(DOMAIN, coordinator.config_entry.data[CONF_HUB_ID])}}
            )
        else:
            self._attr_device_info.update(
                {
                    "identifiers": {(DOMAIN, coordinator.config_entry.unique_id or "")},
                    "via_device": (DOMAIN, coordinator.config_entry.data[CONF_HUB_ID]),
                }
            )
