"""DataUpdateCoordinator for the LG ThinQ device."""

from __future__ import annotations

import logging
from typing import Any

from thinqconnect import ThinQAPIException
from thinqconnect.integration import HABridge

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """LG Device's Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, ha_bridge: HABridge) -> None:
        """Initialize data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{ha_bridge.device.device_id}",
        )

        self.data = {}
        self.api = ha_bridge
        self.device_id = ha_bridge.device.device_id
        self.sub_id = ha_bridge.sub_id

        alias = ha_bridge.device.alias

        # The device name is usually set to 'alias'.
        # But, if the sub_id exists, it will be set to 'alias {sub_id}'.
        # e.g. alias='MyWashTower', sub_id='dryer' then 'MyWashTower dryer'.
        self.device_name = f"{alias} {self.sub_id}" if self.sub_id else alias

        # The unique id is usually set to 'device_id'.
        # But, if the sub_id exists, it will be set to 'device_id_{sub_id}'.
        # e.g. device_id='TQSXXXX', sub_id='dryer' then 'TQSXXXX_dryer'.
        self.unique_id = (
            f"{self.device_id}_{self.sub_id}" if self.sub_id else self.device_id
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Request to the server to update the status from full response data."""
        try:
            return await self.api.fetch_data()
        except ThinQAPIException as e:
            raise UpdateFailed(e) from e

    def refresh_status(self) -> None:
        """Refresh current status."""
        self.async_set_updated_data(self.data)

    def handle_update_status(self, status: dict[str, Any]) -> None:
        """Handle the status received from the mqtt connection."""
        data = self.api.update_status(status)
        if data is not None:
            self.async_set_updated_data(data)

    def handle_notification_message(self, message: str | None) -> None:
        """Handle the status received from the mqtt connection."""
        data = self.api.update_notification(message)
        if data is not None:
            self.async_set_updated_data(data)


async def async_setup_device_coordinator(
    hass: HomeAssistant, ha_bridge: HABridge
) -> DeviceDataUpdateCoordinator:
    """Create DeviceDataUpdateCoordinator and device_api per device."""
    coordinator = DeviceDataUpdateCoordinator(hass, ha_bridge)
    await coordinator.async_refresh()

    _LOGGER.debug(
        "Setup device's coordinator: %s, model:%s",
        coordinator.device_name,
        coordinator.api.device.model_name,
    )
    return coordinator
