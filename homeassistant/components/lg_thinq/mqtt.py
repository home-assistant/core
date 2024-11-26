"""Support for LG ThinQ Connect API."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Any

from thinqconnect import (
    DeviceType,
    ThinQApi,
    ThinQAPIErrorCodes,
    ThinQAPIException,
    ThinQMQTTClient,
)

from homeassistant.core import Event, HomeAssistant

from .const import DEVICE_PUSH_MESSAGE, DEVICE_STATUS_MESSAGE
from .coordinator import DeviceDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ThinQMQTT:
    """A class that implements MQTT connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        thinq_api: ThinQApi,
        client_id: str,
        coordinators: dict[str, DeviceDataUpdateCoordinator],
    ) -> None:
        """Initialize a mqtt."""
        self.hass = hass
        self.thinq_api = thinq_api
        self.client_id = client_id
        self.coordinators = coordinators
        self.client: ThinQMQTTClient | None = None

    async def async_connect(self) -> bool:
        """Create a mqtt client and then try to connect."""
        try:
            self.client = await ThinQMQTTClient(
                self.thinq_api, self.client_id, self.on_message_received
            )
            if self.client is None:
                return False

            # Connect to server and create certificate.
            return await self.client.async_prepare_mqtt()
        except (ThinQAPIException, TypeError, ValueError):
            _LOGGER.exception("Failed to connect")
            return False

    async def async_disconnect(self, event: Event | None = None) -> None:
        """Unregister client and disconnects handlers."""
        await self.async_end_subscribes()

        if self.client is not None:
            try:
                await self.client.async_disconnect()
            except (ThinQAPIException, TypeError, ValueError):
                _LOGGER.exception("Failed to disconnect")

    def _get_failed_device_count(
        self, results: list[dict | BaseException | None]
    ) -> int:
        """Check if there exists errors while performing tasks and then return count."""
        # Note that result code '1207' means 'Already subscribed push'
        # and is not actually fail.
        return sum(
            isinstance(result, (TypeError, ValueError))
            or (
                isinstance(result, ThinQAPIException)
                and result.code != ThinQAPIErrorCodes.ALREADY_SUBSCRIBED_PUSH
            )
            for result in results
        )

    async def async_refresh_subscribe(self, now: datetime | None = None) -> None:
        """Update event subscribes."""
        _LOGGER.debug("async_refresh_subscribe: now=%s", now)

        tasks = [
            self.hass.async_create_task(
                self.thinq_api.async_post_event_subscribe(coordinator.device_id)
            )
            for coordinator in self.coordinators.values()
        ]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            if (count := self._get_failed_device_count(results)) > 0:
                _LOGGER.error("Failed to refresh subscription on %s devices", count)

    async def async_start_subscribes(self) -> None:
        """Start push/event subscribes."""
        _LOGGER.debug("async_start_subscribes")

        if self.client is None:
            _LOGGER.error("Failed to start subscription: No client")
            return

        tasks = [
            self.hass.async_create_task(
                self.thinq_api.async_post_push_subscribe(coordinator.device_id)
            )
            for coordinator in self.coordinators.values()
        ]
        tasks.extend(
            self.hass.async_create_task(
                self.thinq_api.async_post_event_subscribe(coordinator.device_id)
            )
            for coordinator in self.coordinators.values()
        )
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            if (count := self._get_failed_device_count(results)) > 0:
                _LOGGER.error("Failed to start subscription on %s devices", count)

        await self.client.async_connect_mqtt()

    async def async_end_subscribes(self) -> None:
        """Start push/event unsubscribes."""
        _LOGGER.debug("async_end_subscribes")

        tasks = [
            self.hass.async_create_task(
                self.thinq_api.async_delete_push_subscribe(coordinator.device_id)
            )
            for coordinator in self.coordinators.values()
        ]
        tasks.extend(
            self.hass.async_create_task(
                self.thinq_api.async_delete_event_subscribe(coordinator.device_id)
            )
            for coordinator in self.coordinators.values()
        )
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            if (count := self._get_failed_device_count(results)) > 0:
                _LOGGER.error("Failed to end subscription on %s devices", count)

    def on_message_received(
        self,
        topic: str,
        payload: bytes,
        dup: bool,
        qos: Any,
        retain: bool,
        **kwargs: dict,
    ) -> None:
        """Handle the received message that matching the topic."""
        decoded = payload.decode()
        try:
            message = json.loads(decoded)
        except ValueError:
            _LOGGER.error("Failed to parse message: payload=%s", decoded)
            return

        asyncio.run_coroutine_threadsafe(
            self.async_handle_device_event(message), self.hass.loop
        ).result()

    async def async_handle_device_event(self, message: dict) -> None:
        """Handle received mqtt message."""
        unique_id = (
            f"{message["deviceId"]}_{list(message["report"].keys())[0]}"
            if message["deviceType"] == DeviceType.WASHTOWER
            else message["deviceId"]
        )
        coordinator = self.coordinators.get(unique_id)
        if coordinator is None:
            _LOGGER.error("Failed to handle device event: No device")
            return

        _LOGGER.debug(
            "async_handle_device_event: %s, model:%s, message=%s",
            coordinator.device_name,
            coordinator.api.device.model_name,
            message,
        )
        push_type = message.get("pushType")

        if push_type == DEVICE_STATUS_MESSAGE:
            coordinator.handle_update_status(message.get("report", {}))
        elif push_type == DEVICE_PUSH_MESSAGE:
            coordinator.handle_notification_message(message.get("pushCode"))
