"""The IntelliFire integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import pyflume

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_SCAN_INTERVAL = timedelta(minutes=1)


class FlumeNotificationDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for flume notifications."""

    def __init__(self, hass: HomeAssistant, auth) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=NOTIFICATION_SCAN_INTERVAL,
        )
        self.auth = auth
        self.notifications: dict = {}
        self.active_notification_types: list[str] = []

    def _update_lists(self):
        """Query flume for notification list."""
        self.notifications = pyflume.FlumeNotificationList(
            self.auth, read="true"
        ).notification_list
        self.active_notification_types = list(
            {x["extra"]["event_rule_name"] for x in self.notifications}
        )
        _LOGGER.debug("Active Flume Notifications %s", self.active_notification_types)

    async def _async_update_data(self) -> None:
        """Update data.."""
        _LOGGER.debug("Updating Flume Notification")
        try:
            await self.hass.async_add_executor_job(self._update_lists)
        except Exception as ex:
            _LOGGER.error(ex)
            _LOGGER.error("UPDATE ERROR")
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            manufacturer="Flume, Inc.",
            model="Flume Smart Water Monitor",
            identifiers={(DOMAIN, "Messages")},
            name="Flume Notifications",
            configuration_url="https://portal.flumewater.com/notifications",
        )
