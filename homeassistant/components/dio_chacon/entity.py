"""Base entity for the Dio Chacon entity."""

from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import DioChaconDataUpdateCoordinator


class DioChaconEntity(CoordinatorEntity):
    """Implements a common class elements representing the Dio Chacon entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DioChaconDataUpdateCoordinator,
        target_id: str,
        name: str,
        model: str,
        connected: bool,
    ) -> None:
        """Initialize Dio Chacon entity."""
        super().__init__(coordinator)

        self.dio_chacon_client: DIOChaconAPIClient = coordinator.dio_chacon_client

        self._attr_available = connected
        self._target_id = target_id
        self._attr_unique_id = target_id
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._target_id)},
            manufacturer=MANUFACTURER,
            name=name,
            model=model,
        )

    @property
    def coordinator_data(self) -> dict[str, Any] | None:
        """Return the coordinator data for received callback information by filtering on the correct device id."""
        if self.coordinator.data and self.coordinator.data["id"] == self._target_id:
            return self.coordinator.data
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.coordinator_data and self.coordinator_data["connected"]:
            return self.coordinator_data["connected"]
        return self._attr_available
