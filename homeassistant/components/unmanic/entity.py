"""Unmanic entity class."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


class UnmanicEntity(CoordinatorEntity):
    """Class to represent an Unmanic entity."""

    def __init__(self, coordinator, config_entry, device_id):
        """Initialize."""
        self.config_entry = config_entry
        self._device_id = device_id
        super().__init__(coordinator)

    @property
    def device_info(self):
        """Unmanic device information."""

        configuration_url = "https://" if self.coordinator.api.tls else "http://"
        configuration_url += f"{self.coordinator.api.host}:{self.coordinator.api.port}"
        configuration_url += "/unmanic/ui/dashboard/"

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"{NAME} ({self.coordinator.api.host})",
            model=NAME,
            sw_version=self.coordinator.data["version"],
            manufacturer=NAME,
            configuration_url=configuration_url,
        )
