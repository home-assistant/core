"""The IntelliFire integration."""
from __future__ import annotations

from typing import Any

import pyflume
from pyflume import FlumeDeviceList

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DEVICE_SCAN_INTERVAL, DOMAIN, NOTIFICATION_SCAN_INTERVAL


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


class FlumeDeviceConnectionUpdateCoordinator(DataUpdateCoordinator[None]):
    """Date update coordinator to read connected status from Devices endpoint."""

    def __init__(self, hass: HomeAssistant, flume_devices: FlumeDeviceList) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )

        self.flume_devices = flume_devices
        self.connected: dict[str, bool] = {}

    def _update_connectivity(self) -> None:
        """Update device connectivity.."""
        # Update devices
        self.flume_devices.get_devices()

        connections = {}
        for item in self.flume_devices.get_devices():
            connections[item["id"]] = item["connected"]

        self.connected = connections

    async def _async_update_data(self) -> None:
        """Update the device list."""
        try:
            await self.hass.async_add_executor_job(self._update_connectivity)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex


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
        self.active_notifications_by_device: dict = {}
        self.notifications: list[dict[str, Any]]

    def _update_lists(self):
        """Query flume for notification list."""
        self.notifications: list[dict[str, Any]] = pyflume.FlumeNotificationList(
            self.auth, read="true"
        ).notification_list
        _LOGGER.debug("Notifications %s", self.notifications)

        active_notifications_by_device: dict[str, set[str]] = {}

        for notification in self.notifications:
            if (
                not notification.get("device_id")
                or not notification.get("extra")
                or "event_rule_name" not in notification["extra"]
            ):
                continue
            device_id = notification["device_id"]
            rule = notification["extra"]["event_rule_name"]
            active_notifications_by_device.setdefault(device_id, set()).add(rule)

        self.active_notifications_by_device = active_notifications_by_device

        # notifications_by_device: dict[str, set[str]] = {}

        # bridge_status_by_device: dict[str, list[str]] = {}
        # # Process the notification array
        # for item in self.notifications:

        #     device_id = item["device_id"]
        #     rule = item["extra"]["event_rule_name"]

        #     if rule == BRIDGE_NOTIFICATION_RULE:
        #         # Dont process bridge notifications - they are handled separately
        #         bridge_status_by_device.setdefault(device_id, [True]).append(
        #             item["extra"][BRIDGE_NOTIFICATION_KEY]
        #         )
        #     else:
        #         notifications_by_device.setdefault(device_id, set()).add(rule)

        # # For each device look at the last status of the bridge, and if True add BRIDGE_NOTIFICATION_RULE.
        # for device_id in bridge_status_by_device.items():
        #     if bridge_status_by_device[device_id][-1]:
        #         notifications_by_device.setdefault(device_id, set()).add(
        #             BRIDGE_NOTIFICATION_RULE
        #         )
        # self.active_notifications_by_device = notifications_by_device

    async def _async_update_data(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating Flume Notification")
        try:
            await self.hass.async_add_executor_job(self._update_lists)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
