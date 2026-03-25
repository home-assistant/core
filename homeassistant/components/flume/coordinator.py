"""The IntelliFire integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pyflume
from pyflume import FlumeAuth, FlumeData, FlumeDeviceList
from requests import Session

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    DEVICE_CONNECTION_SCAN_INTERVAL,
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    NOTIFICATION_SCAN_INTERVAL,
)


@dataclass
class FlumeRuntimeData:
    """Runtime data for the Flume config entry."""

    devices: FlumeDeviceList
    auth: FlumeAuth
    http_session: Session
    notifications_coordinator: FlumeNotificationDataUpdateCoordinator


type FlumeConfigEntry = ConfigEntry[FlumeRuntimeData]


class FlumeDeviceDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for an individual flume device."""

    config_entry: FlumeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FlumeConfigEntry,
        flume_device: FlumeData,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )

        self.flume_device = flume_device

    async def _async_update_data(self) -> None:
        """Get the latest data from the Flume."""
        try:
            await self.hass.async_add_executor_job(self.flume_device.update_force)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
        _LOGGER.debug(
            "Flume Device Data Update values=%s query_payload=%s",
            self.flume_device.values,
            self.flume_device.query_payload,
        )


class FlumeDeviceConnectionUpdateCoordinator(DataUpdateCoordinator[None]):
    """Date update coordinator to read connected status from Devices endpoint."""

    config_entry: FlumeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FlumeConfigEntry,
        flume_devices: FlumeDeviceList,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_CONNECTION_SCAN_INTERVAL,
        )

        self.flume_devices = flume_devices
        self.connected: dict[str, bool] = {}

    def _update_connectivity(self) -> None:
        """Update device connectivity.."""
        self.connected = {
            device["id"]: device["connected"]
            for device in self.flume_devices.get_devices()
        }
        _LOGGER.debug("Connectivity %s", self.connected)

    async def _async_update_data(self) -> None:
        """Update the device list."""
        try:
            await self.hass.async_add_executor_job(self._update_connectivity)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex


class FlumeNotificationDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Data update coordinator for flume notifications."""

    config_entry: FlumeConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: FlumeConfigEntry, auth: FlumeAuth
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=NOTIFICATION_SCAN_INTERVAL,
        )
        self.auth = auth
        self.active_notifications_by_device: dict[str, set[str]] = {}
        self.notifications: list[dict[str, Any]] = []

    def _update_lists(self) -> None:
        """Query flume for notification list."""
        # Get notifications (read or unread).
        # The related binary sensors (leak detected, high flow, low battery)
        # will be active until the notification is deleted in the Flume app.
        self.notifications = pyflume.FlumeNotificationList(
            self.auth, read=None
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

    async def _async_update_data(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating Flume Notification")
        try:
            await self.hass.async_add_executor_job(self._update_lists)
        except Exception as ex:
            raise UpdateFailed(f"Error communicating with flume API: {ex}") from ex
