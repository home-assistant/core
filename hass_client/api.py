"""Home Assistant websocket API client."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
import logging
import os
from ssl import SSLContext
from typing import Any, cast

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


def _normalize_translation_placeholders(
    placeholders: Any,
) -> dict[str, str] | None:
    """Normalize websocket translation placeholders into Home Assistant format."""
    if not isinstance(placeholders, Mapping):
        return None
    return {str(key): str(value) for key, value in placeholders.items()}


def _build_failed_command(
    message: str,
    *,
    command: str | None,
    code: str | None,
    translation_domain: str | None,
    translation_key: str | None,
    translation_placeholders: dict[str, str] | None,
) -> FailedCommand:
    """Build the generic websocket command failure."""
    return FailedCommand(
        message,
        command=command,
        code=code,
        translation_domain=translation_domain,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
    )


def _build_homeassistant_error(
    exception_type,
    message: str,
    *,
    translation_domain: str | None,
    translation_key: str | None,
    translation_placeholders: dict[str, str] | None,
):
    """Build a Home Assistant exception from websocket translation metadata."""
    if translation_domain and translation_key:
        return exception_type(
            translation_domain=translation_domain,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )
    return exception_type(message)


def _translate_command_error(
    command_message: Mapping[str, Any] | None,
    error: Mapping[str, Any],
) -> Exception:
    """Translate websocket command errors into Home Assistant exceptions when possible."""
    command = command_message.get("type") if command_message else None
    message = str(error.get("message", "Command failed"))
    code = error.get("code")
    code = str(code) if code is not None else None
    translation_domain = error.get("translation_domain")
    translation_domain = (
        str(translation_domain) if translation_domain is not None else None
    )
    translation_key = error.get("translation_key")
    translation_key = str(translation_key) if translation_key is not None else None
    translation_placeholders = _normalize_translation_placeholders(
        error.get("translation_placeholders")
    )

    try:
        import voluptuous as vol

        from homeassistant.components.websocket_api import const as websocket_api_const
        from homeassistant.exceptions import (
            HomeAssistantError,
            ServiceNotFound,
            ServiceValidationError,
            TemplateError,
            Unauthorized,
        )
    except ImportError:
        return _build_failed_command(
            message,
            command=command,
            code=code,
            translation_domain=translation_domain,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )

    if command == "call_service":
        if (
            code == websocket_api_const.ERR_NOT_FOUND
            and translation_key == "service_not_found"
        ):
            domain = translation_placeholders.get("domain") if translation_placeholders else None
            service = (
                translation_placeholders.get("service")
                if translation_placeholders
                else None
            )
            if domain is None and command_message is not None:
                raw_domain = command_message.get("domain")
                if isinstance(raw_domain, str):
                    domain = raw_domain
            if service is None and command_message is not None:
                raw_service = command_message.get("service")
                if isinstance(raw_service, str):
                    service = raw_service
            if domain is not None and service is not None:
                return ServiceNotFound(domain, service)

        if code == websocket_api_const.ERR_INVALID_FORMAT:
            return vol.Invalid(message)

        if code == websocket_api_const.ERR_SERVICE_VALIDATION_ERROR:
            return _build_homeassistant_error(
                ServiceValidationError,
                message,
                translation_domain=translation_domain,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )

        if code == websocket_api_const.ERR_HOME_ASSISTANT_ERROR:
            return _build_homeassistant_error(
                HomeAssistantError,
                message,
                translation_domain=translation_domain,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )

    if code == websocket_api_const.ERR_TEMPLATE_ERROR:
        return TemplateError(message)

    if code == websocket_api_const.ERR_UNAUTHORIZED:
        return Unauthorized()

    return _build_failed_command(
        message,
        command=command,
        code=code,
        translation_domain=translation_domain,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
    )


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
        self._result_messages: dict[int, dict[str, Any]] = {}
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
        return cast(dict[str, Any], await self.send_command("call_service", **payload))

    async def async_get_states(self) -> list[dict[str, Any]]:
        """Fetch all remote states."""
        return cast(list[dict[str, Any]], await self.send_command("get_states"))

    async def async_get_config(self) -> dict[str, Any]:
        """Fetch remote config."""
        return cast(dict[str, Any], await self.send_command("get_config"))

    async def async_get_services(self) -> dict[str, dict[str, Any]]:
        """Fetch remote services."""
        return cast(dict[str, dict[str, Any]], await self.send_command("get_services"))

    async def async_get_entity_registry(self) -> list[dict[str, Any]]:
        """Fetch remote entity registry entries."""
        return cast(
            list[dict[str, Any]],
            await self.send_command("config/entity_registry/list"),
        )

    async def async_get_entity_registry_entry(self, entity_id: str) -> dict[str, Any]:
        """Fetch a single remote entity registry entry."""
        return cast(
            dict[str, Any],
            await self.send_command("config/entity_registry/get", entity_id=entity_id),
        )

    async def send_command(self, command: str, **payload: Any) -> Any:
        """Send a command and await the result."""
        if not self.connected:
            raise NotConnected("Call start() before sending commands")

        future: asyncio.Future[Any] = self._loop.create_future()
        message_id = await self._next_message_id()
        message = {"id": message_id, "type": command, **payload}
        self._result_futures[message_id] = future
        self._result_messages[message_id] = message
        await self._send_json(message)
        try:
            return await future
        finally:
            self._result_futures.pop(message_id, None)
            self._result_messages.pop(message_id, None)

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
        self._result_messages[message_id] = message
        try:
            await self._send_json(message)
            await future
        finally:
            self._result_futures.pop(message_id, None)
            self._result_messages.pop(message_id, None)

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
            future.set_exception(
                _translate_command_error(self._result_messages.get(message_id), error)
            )
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
