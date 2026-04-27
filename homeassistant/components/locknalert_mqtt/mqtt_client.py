"""LocknAlert LocknAlertLocknAlertMQTT runtime transport.

Patterns adapted from Home Assistant LocknAlertLocknAlertMQTT integration:
- one shared broker client lifecycle
- callback fan-out by topic class
- reconnect and re-subscribe strategy
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from paho.mqtt.client import Client, LocknAlertMQTTMessage

from .coordinator import LocknAlertCoordinator
from .const import OFFLINE, ONLINE

_LOGGER = logging.getLogger(__name__)


class LocknAlertMqttClient:
    """Owns LocknAlertLocknAlertMQTT connection for LocknAlert config entry."""

    def __init__(
        self,
        coordinator: LocknAlertCoordinator,
        bridge_id: str,
        prefix: str,
        host: str,
        port: int,
        username: str,
        password: str,
        tls_required: bool,
    ) -> None:
        self._coordinator = coordinator
        self._bridge_id = bridge_id
        self._prefix = prefix.rstrip("/")
        self._host = host
        self._port = port
        self._loop: asyncio.AbstractEventLoop | None = None

        self._client = Client(client_id=f"ha-locknalert-{bridge_id}")
        self._client.username_pw_set(username, password)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        if tls_required:
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    async def async_start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._client.loop_start()
        await asyncio.to_thread(self._client.connect, self._host, self._port, 30)

    async def async_stop(self) -> None:
        try:
            await asyncio.to_thread(self._client.disconnect)
        finally:
            self._client.loop_stop()

    def _topic(self, suffix: str) -> str:
        return f"{self._prefix}/{self._bridge_id}/{suffix}"

    def _on_connect(self, client: Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        _LOGGER.debug("Connected to LocknAlert broker: %s", reason_code)
        client.subscribe('/#', qos=1)

    def _on_disconnect(self, client: Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        _LOGGER.warning("Disconnected from LocknAlert broker: %s", reason_code)
        if self._loop:
            self._loop.call_soon_threadsafe(
                self._coordinator.async_update, "availability", {"state": OFFLINE}
            )

    def _on_message(self, client: Client, userdata: Any, msg: LocknAlertMQTTMessage) -> None:
        if self._loop is None:
            return

        payload_raw = msg.payload.decode("utf-8", errors="ignore")
        try:
            payload: dict[str, Any] = json.loads(payload_raw) if payload_raw.startswith("{") else {"state": payload_raw}
        except json.JSONDecodeError:
            payload = {"state": payload_raw}

        topic = msg.topic.split("/")
        if len(topic) < 4:
            return

        channel = None
        # locknalert/<bridge_id>/<kind>/... pattern
        kind = topic[2]
        if kind == "availability":
            if payload.get("state") not in (ONLINE, OFFLINE):
                payload = {"state": ONLINE if payload_raw.lower() == ONLINE else OFFLINE}
            channel = "availability"
        elif kind == "status":
            channel = "status"
        elif kind in {"zone", "partition", "output", "sensor"} and len(topic) >= 5:
            channel = f"{kind}:{topic[3]}"

        if channel:
            self._loop.call_soon_threadsafe(self._coordinator.async_update, channel, payload)
