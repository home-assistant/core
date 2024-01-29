"""Component providing basic support for Foscam IP cameras."""
from __future__ import annotations

from homeassistant.const import ATTR_HW_VERSION, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FoscamCoordinator


class FoscamEntity(CoordinatorEntity[FoscamCoordinator]):
    """Base entity for Foscam camera."""

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the base Foscam entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Foscam",
        )
        if dev_info := coordinator.data.get("dev_info"):
            self._attr_device_info[ATTR_MODEL] = dev_info["productName"]
            self._attr_device_info[ATTR_SW_VERSION] = dev_info["firmwareVer"]
            self._attr_device_info[ATTR_HW_VERSION] = dev_info["hardwareVer"]
