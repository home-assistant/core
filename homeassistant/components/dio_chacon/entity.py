"""Base entity for the Dio Chacon entity."""

from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER


class DioChaconEntity(Entity):
    """Implements a common class elements representing the Dio Chacon entity."""

    _attr_should_poll = False

    def __init__(
        self, dio_chacon_client: DIOChaconAPIClient, device: dict[str, Any]
    ) -> None:
        """Initialize Dio Chacon entity."""

        self.dio_chacon_client: DIOChaconAPIClient = dio_chacon_client

        self.target_id: str = device["id"]
        self._attr_unique_id: str | None = device["id"]
        self._attr_name: str | None = device["name"]
        self._attr_device_info: DeviceInfo | None = DeviceInfo(
            identifiers={(DOMAIN, self.target_id)},
            manufacturer=MANUFACTURER,
            name=device["name"],
            model=device["model"],
        )

        self._update_attr(device)

    def _update_attr(self, data: dict[str, Any]) -> None:
        """Recomputes the attributes values."""
        # method to be overridden by the child class.
