"""Envertech EVT800 entity."""

from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnvertechEVT800Coordinator


class EnvertechEVT800Entity(CoordinatorEntity[EnvertechEVT800Coordinator]):
    """Envertech EVT800 entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EnvertechEVT800Coordinator) -> None:
        """Initialize Envertech EVT800 entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            configuration_url=f"http://{coordinator.config_entry.data[CONF_IP_ADDRESS]}/",
            manufacturer="Envertech",
            model_id="EVT800",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.client.online
