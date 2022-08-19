"""The IntelliFire integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import pyflume
from pyflume import FlumeData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NOTIFICATION_BRIDGE_DISCONNECT

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_SCAN_INTERVAL = timedelta(minutes=1)
DEVICE_SCAN_INTERVAL = timedelta(minutes=1)


class FlumeDataUpdateCoordinator(DataUpdateCoordinator):
    """Parent class for both Device and Notification update coordinators."""

    pass  # pylint: disable=unnecessary-pass


class FlumeDeviceDataUpdateCoordinator(FlumeDataUpdateCoordinator):
    """Data update coordinator for an individual flume device."""

    def __init__(
        self, hass: HomeAssistant, flume_auth, device_id, device_timezone, http_session
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )
        self.hass = hass

        self.flume_device = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            scan_interval=DEVICE_SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )

    async def _async_update_data(self):
        """Get the latest data from the Flume."""
        _LOGGER.debug("Updating Flume data")
        try:
            await self.hass.async_add_executor_job(self.flume_device.update_force)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
        _LOGGER.debug(
            "Flume update details: %s",
            {
                "values": self.flume_device.values,
                "query_payload": self.flume_device.query_payload,
            },
        )


class FlumeNotificationDataUpdateCoordinator(FlumeDataUpdateCoordinator):
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

            if device_id not in notifications_by_device:
                notifications_by_device[device_id] = {}
            if rule == NOTIFICATION_BRIDGE_DISCONNECT:
                # Bridge notifications are a special case
                # both connect and disconnect register as notifications
                # the last one (by time) will indicate connection state
                notifications_by_device[device_id][rule] = extra["connected"]
            else:
                notifications_by_device[device_id][rule] = True

        self.active_notifications_by_device = notifications_by_device

    async def _async_update_data(self) -> None:
        """Update data.."""
        _LOGGER.debug("Updating Flume Notification")
        try:
            await self.hass.async_add_executor_job(self._update_lists)
        except Exception as ex:
            _LOGGER.error(ex)
            _LOGGER.error("UPDATE ERROR")
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
