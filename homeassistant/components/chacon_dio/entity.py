"""Base entity for the Chacon Dio entity."""

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class ChaconDioEntity(Entity):
    """Implements a common class elements representing the Chacon Dio entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, client: DIOChaconAPIClient, device: dict[str, Any]) -> None:
        """Initialize Chacon Dio entity."""

        self.client = client

        self.target_id: str = device["id"]
        self._attr_unique_id = self.target_id
        self._attr_device_info: DeviceInfo | None = DeviceInfo(
            identifiers={(DOMAIN, self.target_id)},
            manufacturer=MANUFACTURER,
            name=device["name"],
            model=device["model"],
        )

        self._update_attr(device)

    def _update_attr(self, data: dict[str, Any]) -> None:
        """Recomputes the attributes values."""

    async def async_added_to_hass(self) -> None:
        """Register the callback for server side events."""
        await super().async_added_to_hass()
        self.client.set_callback_device_state_by_device(
            self.target_id, self.callback_device_state
        )

    def callback_device_state(self, data: dict[str, Any]) -> None:
        """Receive callback for device state notification pushed from the server."""

        _LOGGER.debug("Data received from server %s", data)
        self._update_attr(data)
        self.async_write_ha_state()
