"""Message routing coordinators for handling NASweb push notifications."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from aiohttp.web import Request, Response
from webio_api import WebioAPI
from webio_api.const import KEY_DEVICE_SERIAL, KEY_OUTPUTS, KEY_TYPE, TYPE_STATUS_UPDATE

from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.update_coordinator import BaseDataUpdateCoordinatorProtocol

from .const import STATUS_UPDATE_MAX_TIME_INTERVAL

_LOGGER = logging.getLogger(__name__)


class NotificationCoordinator:
    """Coordinator redirecting push notifications for this integration to appropriate NASwebCoordinator."""

    def __init__(self) -> None:
        """Initialize coordinator."""
        self._coordinators: dict[str, NASwebCoordinator] = {}

    def add_coordinator(self, serial: str, coordinator: NASwebCoordinator) -> None:
        """Add NASwebCoordinator to possible notification targets."""
        self._coordinators[serial] = coordinator
        _LOGGER.debug("Added NASwebCoordinator for NASweb[%s]", serial)

    def remove_coordinator(self, serial: str) -> None:
        """Remove NASwebCoordinator from possible notification targets."""
        self._coordinators.pop(serial)
        _LOGGER.debug("Removed NASwebCoordinator for NASweb[%s]", serial)

    def has_coordinators(self) -> bool:
        """Check if there is any registered coordinator for push notifications."""
        return len(self._coordinators) > 0

    async def check_connection(self, serial: str) -> bool:
        """Wait for first status update to confirm connection with NASweb."""
        nasweb_coordinator = self._coordinators.get(serial)
        if nasweb_coordinator is None:
            _LOGGER.error("Cannot check connection. No device match serial number")
            return False
        for counter in range(10):
            _LOGGER.debug("Checking connection with: %s (%s)", serial, counter)
            if nasweb_coordinator.is_connection_confirmed():
                return True
            await asyncio.sleep(1)
        return False

    async def handle_webhook_request(
        self, hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        """Handle webhook request from Push API."""
        if not self.has_coordinators():
            return None
        notification = await request.json()
        serial = notification.get(KEY_DEVICE_SERIAL, None)
        _LOGGER.debug("Received push: %s", notification)
        if serial is None:
            _LOGGER.warning("Received notification without nasweb identifier")
            return None
        nasweb_coordinator = self._coordinators.get(serial)
        if nasweb_coordinator is None:
            _LOGGER.warning("Received notification for not registered nasweb")
            return None
        await nasweb_coordinator.handle_push_notification(notification)
        return Response(body='{"response": "ok"}', content_type="application/json")


class NASwebCoordinator(BaseDataUpdateCoordinatorProtocol):
    """Coordinator managing status of single NASweb device.

    Since status updates are managed through push notifications, this class schedules
    periodic checks to ensure that devices are marked unavailable if updates
    haven't been received for a prolonged period.
    """

    def __init__(
        self, hass: HomeAssistant, webio_api: WebioAPI, name: str = "NASweb[default]"
    ) -> None:
        """Initialize NASweb coordinator."""
        self._hass = hass
        self.name = name
        self.webio_api = webio_api
        self._last_update: float | None = None
        job_name = f"NASwebCoordinator[{name}]"
        self._job = HassJob(self._handle_max_update_interval, job_name)
        self._unsub_last_update_check: CALLBACK_TYPE | None = None
        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}
        data: dict[str, Any] = {}
        data[KEY_OUTPUTS] = self.webio_api.outputs
        self.async_set_updated_data(data)

    def is_connection_confirmed(self) -> bool:
        """Check whether coordinator received status update from NASweb."""
        return self._last_update is not None

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""
        schedule_update_check = not self._listeners

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.pop(remove_listener)
            if not self._listeners:
                self._async_unsub_last_update_check()

        self._listeners[remove_listener] = (update_callback, context)
        # This is the first listener, set up interval.
        if schedule_update_check:
            self._schedule_last_update_check()
        return remove_listener

    @callback
    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Update data and notify listeners."""
        self.data = data
        self.last_update = self._hass.loop.time()
        _LOGGER.debug("Updated %s data", self.name)
        if self._listeners:
            self._schedule_last_update_check()
        self.async_update_listeners()

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback, _ in list(self._listeners.values()):
            update_callback()

    async def _handle_max_update_interval(self, now: datetime) -> None:
        """Handle max update interval occurrence.

        This method is called when `STATUS_UPDATE_MAX_TIME_INTERVAL` has passed without
        receiving a status update. It only needs to trigger state update of entities
        which then change their state accordingly.
        """
        self._unsub_last_update_check = None
        if self._listeners:
            self.async_update_listeners()

    def _schedule_last_update_check(self) -> None:
        """Schedule a task to trigger entities state update after `STATUS_UPDATE_MAX_TIME_INTERVAL`.

        This method schedules a task (`_handle_max_update_interval`) to be executed after
        `STATUS_UPDATE_MAX_TIME_INTERVAL` seconds without status update, which enables entities
        to change their state to unavailable. After each status update this task is rescheduled.
        """
        self._async_unsub_last_update_check()
        now = self._hass.loop.time()
        next_check = (
            now + timedelta(seconds=STATUS_UPDATE_MAX_TIME_INTERVAL).total_seconds()
        )
        self._unsub_last_update_check = event.async_call_at(
            self._hass,
            self._job,
            next_check,
        )

    def _async_unsub_last_update_check(self) -> None:
        """Cancel any scheduled update check call."""
        if self._unsub_last_update_check:
            self._unsub_last_update_check()
            self._unsub_last_update_check = None

    async def handle_push_notification(self, notification: dict) -> None:
        """Handle incoming push notification from NASweb."""
        msg_type = notification.get(KEY_TYPE)
        _LOGGER.debug("Received push notification: %s", msg_type)

        if msg_type == TYPE_STATUS_UPDATE:
            await self.process_status_update(notification)
            self._last_update = time.time()

    async def process_status_update(self, new_status: dict) -> None:
        """Process status update from NASweb."""
        self.webio_api.update_device_status(new_status)
        new_data = {KEY_OUTPUTS: self.webio_api.outputs}
        self.async_set_updated_data(new_data)
