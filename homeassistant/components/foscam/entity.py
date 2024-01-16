"""Component providing basic support for Foscam IP cameras."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import FoscamCoordinator


class FoscamEntity(Entity):
    """Base entity for Foscam camera."""

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the base Foscam entity."""

        self._username = config_entry.data[CONF_USERNAME]
        self._password = config_entry.data[CONF_PASSWORD]

        dev_info = coordinator.data.get("dev_info", None)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Foscam",
            name=config_entry.title,
        )
        if dev_info := coordinator.data.get("dev_info"):
            self._attr_device_info["model"] = dev_info["productName"]
            self._attr_device_info["sw_version"] = dev_info["firmwareVer"]
            self._attr_device_info["hw_version"] = dev_info["hardwareVer"]
