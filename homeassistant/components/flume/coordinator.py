"""The IntelliFire integration."""
from __future__ import annotations

import pyflume

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    NOTIFICATION_BRIDGE_DISCONNECT,
    NOTIFICATION_SCAN_INTERVAL,
)


class FlumeDeviceDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for an individual flume device."""

    def __init__(self, hass: HomeAssistant, flume_device) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )

        self.flume_device = flume_device

    async def _async_update_data(self) -> None:
        """Get the latest data from the Flume."""
        _LOGGER.debug("Updating Flume data")
        try:
            await self.hass.async_add_executor_job(self.flume_device.update_force)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
        _LOGGER.debug(
            "Flume update details: values=%s query_payload=%s",
            self.flume_device.values,
            self.flume_device.query_payload,
        )


class FlumeNotificationDataUpdateCoordinator(DataUpdateCoordinator[None]):
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
        self.active_notifications_by_device: dict = {}

    def _update_lists(self):
        """Query flume for notification list."""
        self.notifications = pyflume.FlumeNotificationList(
            self.auth, read="true"
        ).notification_list
        _LOGGER.debug("Notifications %s", self.notifications)

        notifications_by_device = {}

        # Reformat notificatinos to correct format
        for notification in self.notifications:
            device_id = notification["device_id"]
            extra = notification["extra"]
            rule = notification["extra"]["event_rule_name"]

            device_notifications = notifications_by_device.setdefault(device_id, {})
            if rule == NOTIFICATION_BRIDGE_DISCONNECT:
                # Bridge notifications are a special case
                # both connect and disconnect register as notifications
                # the last one (by time) will indicate connection state
                device_notifications[rule] = extra["connected"]
            else:
                device_notifications[rule] = True

        self.active_notifications_by_device = notifications_by_device

    async def _async_update_data(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating Flume Notification")
        try:
            await self.hass.async_add_executor_job(self._update_lists)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
