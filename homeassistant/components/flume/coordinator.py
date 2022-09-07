"""The IntelliFire integration."""
from __future__ import annotations

import pyflume

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    BRIDGE_NOTIFICATION_KEY,
    BRIDGE_NOTIFICATION_RULE,
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
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

        # The list of notifications returned by API will be in chronological order and there may be
        # multiple notifications of the same type (such as High Flow). The only special
        # case here is bridge notifications: NOTIFICATION_BRIDGE_DISCONNECT, which will be either True
        # or False as indicated in the ["extra"][BRIDGE_NOTIFICATION_KEY].
        # full_notification_info = {}

        notifications_by_device: dict[str, set[str]] = {}

        for item in self.notifications:

            device_id = item["device_id"]
            rule = item["extra"]["event_rule_name"]

            # Because bridge is a disconnect notification, True = disconnected - its value needs to be reversed
            # all other notifications will be not False ... aka True
            value = not item["extra"].get(BRIDGE_NOTIFICATION_KEY, False)

            if value:
                notifications_by_device.setdefault(
                    device_id, {BRIDGE_NOTIFICATION_RULE}
                ).add(rule)

            if rule == BRIDGE_NOTIFICATION_RULE:
                # If bridge is connected the rule should be present in the notification list
                # if disconnected the rule should not be present
                if value:
                    notifications_by_device[device_id].discard(rule)
                    _LOGGER.debug(
                        "Processed bridge disconnect event - removing %s from notification list",
                        BRIDGE_NOTIFICATION_RULE,
                    )
                else:
                    notifications_by_device[device_id].add(BRIDGE_NOTIFICATION_RULE)
                    _LOGGER.debug(
                        "Processed bridge connect event - adding %s from notification list",
                        BRIDGE_NOTIFICATION_RULE,
                    )

        self.active_notifications_by_device = notifications_by_device

    async def _async_update_data(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating Flume Notification")
        try:
            await self.hass.async_add_executor_job(self._update_lists)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
