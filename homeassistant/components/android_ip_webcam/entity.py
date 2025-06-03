"""Base class for Android IP Webcam entities."""

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AndroidIPCamDataUpdateCoordinator


class AndroidIPCamBaseEntity(CoordinatorEntity[AndroidIPCamDataUpdateCoordinator]):
    """Base class for Android IP Webcam entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.cam = coordinator.cam
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.data.get(CONF_NAME)
            or coordinator.config_entry.data[CONF_HOST],
        )
