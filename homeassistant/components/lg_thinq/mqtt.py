"""Support for LG ThinQ Connect API."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Any

from thinqconnect import ThinQApi, ThinQMQTTClient

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
        coordinator_map: dict[str, DeviceDataUpdateCoordinator],
    ) -> None:
        """Initialize a mqtt client."""
        self.hass = hass
        self.thinq_api = thinq_api
        self.client_id = client_id
        self.coordinator_map = coordinator_map
        self.client: ThinQMQTTClient | None = None

    async def async_connect_and_subscribe(self) -> bool:
        """Create client api instance and try to subscribe."""
        self.client = await ThinQMQTTClient(
            thinq_api=self.thinq_api,
            client_id=self.client_id,
            on_message_received=self.on_message_received,
            on_connection_interrupted=None,
            on_connection_success=None,
            on_connection_failure=None,
            on_connection_closed=None,
        )

        if self.client is None:
            return False

        # Connect to server and create certificate.
        return await self.client.async_prepare_mqtt()

    async def async_disconnect(self, event: Event | None = None) -> None:
        """Unregister client and disconnects handlers."""
        await self.async_end_subscribes()
        if self.client is not None:
            await self.client.async_disconnect()

    async def async_refresh_subscribe(self, now: datetime | None = None) -> None:
        """Update event subscribes."""
        _LOGGER.debug("async_refresh_subscribe: now=%s", now)
        try:
            tasks = [
                self.hass.async_create_task(
                    self.thinq_api.async_post_event_subscribe(coordinator.device_id)
                )
                for coordinator in self.coordinator_map.values()
            ]
            if tasks:
                await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to refresh subscription %s", exc)

    async def async_start_subscribes(self) -> None:
        """Start push/event subscribes."""
        _LOGGER.debug("async_start_subscribes")
        if self.client is None:
            _LOGGER.warning("Failed to start subscription: No client")
            return
        try:
            tasks = [
                self.hass.async_create_task(
                    self.thinq_api.async_post_push_subscribe(coordinator.device_id)
                )
                for coordinator in self.coordinator_map.values()
            ]
            tasks.extend(
                [
                    self.hass.async_create_task(
                        self.thinq_api.async_post_event_subscribe(coordinator.device_id)
                    )
                    for coordinator in self.coordinator_map.values()
                ]
            )
            if tasks:
                await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to start subscription %s", exc)
        finally:
            await self.client.async_connect_mqtt()

    async def async_end_subscribes(self) -> None:
        """Start push/event unsubscribes."""
        _LOGGER.debug("async_end_subscribes")
        try:
            tasks = [
                self.hass.async_create_task(
                    self.thinq_api.async_delete_push_subscribe(coordinator.device_id)
                )
                for coordinator in self.coordinator_map.values()
            ]
            tasks.extend(
                [
                    self.hass.async_create_task(
                        self.thinq_api.async_delete_event_subscribe(
                            coordinator.device_id
                        )
                    )
                    for coordinator in self.coordinator_map.values()
                ]
            )
            if tasks:
                await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to delete subscription %s", exc)

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
            received = json.loads(decoded)
        except ValueError:
            _LOGGER.error("Failed to parse message: payload=%s", decoded)
            return

        asyncio.run_coroutine_threadsafe(
            self.async_handle_device_event(received), self.hass.loop
        ).result()

    async def async_handle_device_event(self, message: dict[str, Any | None]) -> None:
        """Handle received mqtt message."""
        device_id = message.get("deviceId")
        coordinator = self.coordinator_map[str(device_id)]
        if coordinator is None:
            _LOGGER.error("Failed to handle device event: No device")
            return

        push_type = message.get("pushType")
        _LOGGER.debug("async_handle_device_event %s", message)
        if push_type == DEVICE_STATUS_MESSAGE:
            coordinator.handle_update_status(message.get("report", dict[str, Any]()))
        elif push_type == DEVICE_PUSH_MESSAGE:
            coordinator.handle_notification_message(message.get("pushCode"))
