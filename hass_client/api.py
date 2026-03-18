"""Home Assistant websocket API client."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import os
from ssl import SSLContext
from typing import Any

import aiohttp
from aiohttp import (
    ClientSession,
    ClientWebSocketResponse,
    Fingerprint,
    TCPConnector,
    WSMsgType,
    client_exceptions,
)

from .exceptions import (
    AuthenticationFailed,
    CannotConnect,
    ConnectionFailed,
    ConnectionFailedDueToLargeMessage,
    FailedCommand,
    InvalidMessage,
    NotConnected,
)

LOGGER = logging.getLogger(__name__)
MAX_MESSAGE_SIZE = 16 * 1024 * 1024
MATCH_ALL = "*"

SubscriptionCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class HomeAssistantAPI:
    """Async websocket client for Home Assistant."""

    def __init__(
        self,
        websocket_url: str,
        token: str | None,
        aiohttp_session: ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._websocket_url = websocket_url
        self._token = token
        self._loop = asyncio.get_running_loop()
        self._http_session_provided = aiohttp_session is not None
        self._http_session = aiohttp_session
        self._client: ClientWebSocketResponse | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._shutdown_complete: asyncio.Event | None = None
        self._subscriptions: dict[int, tuple[dict[str, Any], SubscriptionCallback]] = {}
        self._result_futures: dict[int, asyncio.Future[Any]] = {}
        self._last_msg_id = 1
        self._msg_id_lock = asyncio.Lock()
        self._version: str | None = None

    @property
    def connected(self) -> bool:
        """Return if the websocket is connected."""
        return self._client is not None and not self._client.closed

    @property
    def version(self) -> str | None:
        """Return the remote Home Assistant version."""
        return self._version

    async def start(self, ssl: SSLContext | bool | Fingerprint | None = True) -> None:
        """Connect and start the listener."""
        await self.connect(ssl=ssl)
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = self._loop.create_task(self._listen())

    async def stop(self) -> None:
        """Stop the listener and disconnect."""
        if not self.connected and self._listener_task is None:
            return
        await self.disconnect()
        if self._listener_task is not None:
            await self._listener_task
            self._listener_task = None

    async def connect(
        self, ssl: SSLContext | bool | Fingerprint | None = True
    ) -> None:
        """Connect to the websocket server."""
        if self.connected:
            return

        if not self._http_session_provided and self._http_session is None:
            self._http_session = ClientSession(
                connector=TCPConnector(enable_cleanup_closed=True)
            )

        ws_token = self._token or os.environ.get("HASSIO_TOKEN")
        if ws_token is None:
            raise AuthenticationFailed("No Home Assistant access token provided")

        try:
            assert self._http_session is not None
            self._client = await self._http_session.ws_connect(
                self._websocket_url,
                heartbeat=55,
                max_msg_size=MAX_MESSAGE_SIZE,
                ssl=ssl,
            )
            hello = await self._client.receive_json()
            if hello.get("type") != "auth_required":
                raise InvalidMessage(f"Unexpected auth hello: {hello}")
            self._version = hello.get("ha_version")
            await self._client.send_json({"type": "auth", "access_token": ws_token})
            auth_result = await self._client.receive_json()
            if auth_result.get("type") != "auth_ok":
                await self._client.close()
                raise AuthenticationFailed(
                    auth_result.get("message", "Authentication failed")
                )
        except (
            client_exceptions.WSServerHandshakeError,
            client_exceptions.ClientError,
        ) as err:
            raise CannotConnect(err) from err

    async def disconnect(self) -> None:
        """Disconnect from Home Assistant."""
        if self._client is None:
            return

        self._shutdown_complete = asyncio.Event()
        await self._client.close()
        await self._shutdown_complete.wait()
        self._client = None

        if not self._http_session_provided and self._http_session is not None:
            await self._http_session.close()
            self._http_session = None

    async def async_call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> dict[str, Any]:
        """Call a Home Assistant service over the websocket API."""
        payload: dict[str, Any] = {
            "domain": domain,
            "service": service,
            "return_response": return_response,
        }
        if service_data:
            payload["service_data"] = service_data
        if target:
            payload["target"] = target
        result = await self.send_command("call_service", **payload)
        if not isinstance(result, dict):
            raise InvalidMessage(f"Unexpected call_service result: {result!r}")
        return result

    async def async_get_states(self) -> list[dict[str, Any]]:
        """Fetch all remote states."""
        result = await self.send_command("get_states")
        if not isinstance(result, list):
            raise InvalidMessage(f"Unexpected get_states result: {result!r}")
        return result

    async def async_get_config(self) -> dict[str, Any]:
        """Fetch remote config."""
        result = await self.send_command("get_config")
        if not isinstance(result, dict):
            raise InvalidMessage(f"Unexpected get_config result: {result!r}")
        return result

    async def async_get_services(self) -> dict[str, dict[str, Any]]:
        """Fetch remote services."""
        result = await self.send_command("get_services")
        if not isinstance(result, dict):
            raise InvalidMessage(f"Unexpected get_services result: {result!r}")
        return result

    async def async_get_entity_registry(self) -> list[dict[str, Any]]:
        """Fetch remote entity registry entries."""
        result = await self.send_command("config/entity_registry/list")
        if not isinstance(result, list):
            raise InvalidMessage(
                f"Unexpected config/entity_registry/list result: {result!r}"
            )
        return result

    async def async_get_entity_registry_entry(self, entity_id: str) -> dict[str, Any]:
        """Fetch a single remote entity registry entry."""
        result = await self.send_command("config/entity_registry/get", entity_id=entity_id)
        if not isinstance(result, dict):
            raise InvalidMessage(
                f"Unexpected config/entity_registry/get result: {result!r}"
            )
        return result

    async def send_command(self, command: str, **payload: Any) -> Any:
        """Send a command and await the result."""
        if not self.connected:
            raise NotConnected("Call start() before sending commands")

        future: asyncio.Future[Any] = self._loop.create_future()
        message_id = await self._next_message_id()
        self._result_futures[message_id] = future
        await self._send_json({"id": message_id, "type": command, **payload})
        try:
            return await future
        finally:
            self._result_futures.pop(message_id, None)

    async def send_command_no_wait(self, command: str, **payload: Any) -> None:
        """Send a command without waiting for the result."""
        if not self.connected:
            raise NotConnected("Call start() before sending commands")
        message_id = await self._next_message_id()
        await self._send_json({"id": message_id, "type": command, **payload})

    async def subscribe_events(
        self,
        callback: SubscriptionCallback,
        event_type: str = MATCH_ALL,
    ) -> Callable[[], None]:
        """Subscribe to Home Assistant events."""
        return await self.subscribe(callback, "subscribe_events", event_type=event_type)

    async def subscribe_entities(
        self,
        callback: SubscriptionCallback,
        entity_ids: list[str],
    ) -> Callable[[], None]:
        """Subscribe to entity websocket updates."""
        return await self.subscribe(
            callback, "subscribe_entities", entity_ids=entity_ids
        )

    async def subscribe(
        self,
        callback: SubscriptionCallback,
        command: str,
        **payload: Any,
    ) -> Callable[[], None]:
        """Register a websocket subscription."""
        message_id = await self._next_message_id()
        message = {"id": message_id, "type": command, **payload}

        future: asyncio.Future[Any] = self._loop.create_future()
        self._result_futures[message_id] = future
        try:
            await self._send_json(message)
            await future
        finally:
            self._result_futures.pop(message_id, None)

        self._subscriptions[message_id] = (message, callback)

        def unsubscribe() -> None:
            """Remove the subscription and unsubscribe remotely."""
            message = self._subscriptions.pop(message_id, None)
            if message is None:
                return
            if command == "subscribe_events":
                self._loop.create_task(
                    self.send_command_no_wait(
                        "unsubscribe_events", subscription=message_id
                    )
                )

        return unsubscribe

    async def _listen(self) -> None:
        """Process inbound websocket frames."""
        assert self._client is not None

        try:
            while not self._client.closed:
                msg = await self._client.receive()

                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.CLOSING):
                    break

                if msg.type == WSMsgType.ERROR:
                    if msg.data.code == aiohttp.WSCloseCode.MESSAGE_TOO_BIG:
                        raise ConnectionFailedDueToLargeMessage
                    raise ConnectionFailed

                if msg.type != WSMsgType.TEXT:
                    raise InvalidMessage(f"Unexpected websocket message type: {msg.type}")

                try:
                    data = msg.json()
                except ValueError as err:
                    raise InvalidMessage("Received invalid JSON") from err

                self._handle_message(data)
        finally:
            for future in self._result_futures.values():
                if not future.done():
                    future.cancel()

            if self._shutdown_complete is not None:
                self._shutdown_complete.set()

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Handle an inbound websocket message."""
        if message.get("type") == "result":
            message_id = message["id"]
            future = self._result_futures.get(message_id)
            if future is None:
                return
            if message.get("success"):
                future.set_result(message.get("result"))
                return
            error = message.get("error", {})
            future.set_exception(FailedCommand(error.get("message", "Command failed")))
            return

        subscription_id = message.get("id")
        if subscription_id in self._subscriptions:
            callback = self._subscriptions[subscription_id][1]
            result = callback(message)
            if asyncio.iscoroutine(result):
                self._loop.create_task(result)
            return

        LOGGER.debug("Ignoring unexpected websocket message: %s", message)

    async def _send_json(self, message: dict[str, Any]) -> None:
        """Send a websocket JSON message."""
        if not self.connected or self._client is None:
            raise NotConnected("The websocket client is not connected")
        await self._client.send_json(message)

    async def _next_message_id(self) -> int:
        """Allocate the next websocket message id."""
        async with self._msg_id_lock:
            self._last_msg_id += 1
            return self._last_msg_id
