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
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to connect: %s", exc)
            return False

    async def async_disconnect(self, event: Event | None = None) -> None:
        """Unregister client and disconnects handlers."""
        await self.async_end_subscribes()

        if self.client is not None:
            try:
                await self.client.async_disconnect()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.error("Failed to disconnect: %s", exc)

    async def async_refresh_subscribe(self, now: datetime | None = None) -> None:
        """Update event subscribes."""
        _LOGGER.debug("async_refresh_subscribe: now=%s", now)

        try:
            tasks = [
                self.hass.async_create_task(
                    self.thinq_api.async_post_event_subscribe(coordinator.device_id)
                )
                for coordinator in self.coordinators.values()
            ]
            if tasks:
                await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to refresh subscription: %s", exc)

    async def async_start_subscribes(self) -> None:
        """Start push/event subscribes."""
        _LOGGER.debug("async_start_subscribes")

        if self.client is None:
            _LOGGER.error("Failed to start subscription: No client")
            return

        try:
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
                await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to start subscription: %s", exc)
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
                for coordinator in self.coordinators.values()
            ]
            tasks.extend(
                self.hass.async_create_task(
                    self.thinq_api.async_delete_event_subscribe(coordinator.device_id)
                )
                for coordinator in self.coordinators.values()
            )
            if tasks:
                await asyncio.gather(*tasks)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Failed to delete subscription: %s", exc)

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
        _LOGGER.debug("async_handle_device_event: message=%s", message)

        device_id = str(message.get("deviceId", ""))
        coordinator = self.coordinators.get(device_id)
        if coordinator is None:
            _LOGGER.error("Failed to handle device event: No device")
            return

        push_type = message.get("pushType")

        if push_type == DEVICE_STATUS_MESSAGE:
            coordinator.handle_update_status(message.get("report", {}))
        elif push_type == DEVICE_PUSH_MESSAGE:
            coordinator.handle_notification_message(message.get("pushCode"))
