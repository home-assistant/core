"""Model Context Protocol transport for SSE and Streamable HTTP."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound, HTTPServiceUnavailable
from aiohttp_sse import sse_response
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import types
from mcp.shared.message import SessionMessage
from multidict import CIMultiDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.components import conversation
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm

from .const import DOMAIN, MESSAGES_API, SSE_API, STREAMABLE_HTTP_API
from .runtime import MCPServerRuntime
from .session import Session
from .server import create_server

_LOGGER = logging.getLogger(__name__)

ASGIHandler = Callable[
    [
        dict[str, Any],
        Callable[[], Awaitable[dict[str, Any]]],
        Callable[[dict[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the HTTP transports."""

    hass.http.register_view(ModelContextProtocolSSEView())
    hass.http.register_view(ModelContextProtocolMessagesView())
    hass.http.register_view(ModelContextProtocolStreamableHTTPView())


def async_get_config_entry(hass: HomeAssistant) -> ConfigEntry[MCPServerRuntime]:
    """Get the first enabled MCP server config entry."""

    config_entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not config_entries:
        raise HTTPNotFound(text="Model Context Protocol server is not configured")
    if len(config_entries) > 1:
        raise HTTPNotFound(text="Found multiple Model Context Protocol configurations")
    entry = config_entries[0]
    if entry.runtime_data is None:
        raise HTTPServiceUnavailable(
            text="Model Context Protocol server is still initialising"
        )
    return cast(ConfigEntry[MCPServerRuntime], entry)


class ModelContextProtocolSSEView(HomeAssistantView):
    """Model Context Protocol SSE endpoint."""

    name = f"{DOMAIN}:sse"
    url = SSE_API

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Process SSE messages for the Model Context Protocol."""

        hass = request.app[KEY_HASS]
        entry = async_get_config_entry(hass)
        runtime: MCPServerRuntime = entry.runtime_data
        session_manager = runtime.session_manager

        llm_context = llm.LLMContext(
            platform=DOMAIN,
            context=self.context(request),
            language="*",
            assistant=conversation.DOMAIN,
            device_id=None,
        )
        llm_api_id = entry.data[CONF_LLM_HASS_API]
        server = await create_server(
            hass,
            llm_api_id,
            llm_context,
            auth_settings=runtime.auth_settings,
            token_verifier=runtime.token_verifier,
        )
        options = await hass.async_add_executor_job(
            server._mcp_server.create_initialization_options
        )  # noqa: SLF001

        read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
        read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream: MemoryObjectSendStream[SessionMessage]
        write_stream_reader: MemoryObjectReceiveStream[SessionMessage]
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        async with (
            sse_response(request) as response,
            session_manager.create(Session(read_stream_writer)) as session_id,
        ):
            session_uri = MESSAGES_API.format(session_id=session_id)
            _LOGGER.debug("Sending SSE endpoint: %s", session_uri)
            await response.send(session_uri, event="endpoint")

            async def sse_reader() -> None:
                """Forward MCP server responses to the client."""

                async for session_message in write_stream_reader:
                    _LOGGER.debug("Sending SSE message: %s", session_message)
                    await response.send(
                        session_message.message.model_dump_json(
                            by_alias=True, exclude_none=True
                        ),
                        event="message",
                    )

            async with anyio.create_task_group() as tg:
                tg.start_soon(sse_reader)
                await server._mcp_server.run(read_stream, write_stream, options)  # noqa: SLF001

            return response


class ModelContextProtocolMessagesView(HomeAssistantView):
    """Model Context Protocol messages endpoint."""

    name = f"{DOMAIN}:messages"
    url = MESSAGES_API

    async def post(self, request: web.Request, session_id: str) -> web.StreamResponse:
        """Process incoming messages for the Model Context Protocol."""

        hass = request.app[KEY_HASS]
        entry = async_get_config_entry(hass)
        runtime: MCPServerRuntime = entry.runtime_data
        session_manager = runtime.session_manager

        session = session_manager.get(session_id)
        if session is None:
            _LOGGER.info("Could not find session ID: '%s'", session_id)
            raise HTTPNotFound(text=f"Could not find session ID '{session_id}'")

        json_data = await request.json()
        try:
            message = types.JSONRPCMessage.model_validate(json_data)
        except ValueError as err:
            _LOGGER.info("Failed to parse message: %s", err)
            raise HTTPBadRequest(text="Could not parse message") from err

        _LOGGER.debug("Received client message: %s", message)
        await session.read_stream_writer.send(SessionMessage(message))
        return web.Response(status=200)


class ModelContextProtocolStreamableHTTPView(HomeAssistantView):
    """Streamable HTTP transport endpoint."""

    name = f"{DOMAIN}:streamable-http"
    url = STREAMABLE_HTTP_API
    requires_auth = False

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Handle GET requests for streamable HTTP transport."""
        return await self._handle(request)

    async def post(self, request: web.Request) -> web.StreamResponse:
        """Handle POST requests for streamable HTTP transport."""
        return await self._handle(request)

    async def delete(self, request: web.Request) -> web.StreamResponse:
        """Handle DELETE requests for streamable HTTP transport."""
        return await self._handle(request)

    async def options(self, request: web.Request) -> web.StreamResponse:
        """Handle CORS pre-flight checks for web clients."""
        origin = request.headers.get("Origin", "*")
        allow_headers = request.headers.get(
            "Access-Control-Request-Headers",
            "Authorization, MCP-Session-ID, Content-Type",
        )
        response = web.Response(status=204)
        _apply_cors_headers(
            response, request, origin_override=origin, allow_headers=allow_headers
        )
        response.headers.setdefault(
            "Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS"
        )
        return response

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        hass = request.app[KEY_HASS]
        entry = async_get_config_entry(hass)
        runtime: MCPServerRuntime = entry.runtime_data

        async def handler(
            scope: dict[str, Any],
            receive: Callable[[], Awaitable[dict[str, Any]]],
            send: Callable[[dict[str, Any]], Awaitable[None]],
        ) -> None:
            await runtime.streamable_manager.handle_request(scope, receive, send)

        try:
            return await _call_asgi(handler, request)
        except RuntimeError as err:
            _LOGGER.error("Streamable HTTP manager not running: %s", err)
            raise HTTPServiceUnavailable(
                text="Streamable HTTP transport is unavailable"
            ) from err


async def _call_asgi(handler: ASGIHandler, request: web.Request) -> web.StreamResponse:
    """Invoke an ASGI handler from an aiohttp request."""

    body = await request.read()
    body_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2)
    await body_queue.put({"type": "http.request", "body": body, "more_body": False})
    disconnect_event = asyncio.Event()

    async def receive() -> dict[str, Any]:
        if not body_queue.empty():
            return await body_queue.get()
        await disconnect_event.wait()
        return {"type": "http.disconnect"}

    loop = asyncio.get_running_loop()
    response_future: asyncio.Future[web.StreamResponse] = loop.create_future()
    response_status = 200
    response_headers: list[tuple[bytes, bytes]] = []
    stream_response: web.StreamResponse | None = None

    async def send(message: dict[str, Any]) -> None:
        nonlocal response_status, response_headers, stream_response
        message_type = message.get("type")

        if message_type == "http.response.start":
            response_status = message.get("status", 200)
            response_headers = message.get("headers", [])
            return

        if message_type != "http.response.body":
            _LOGGER.debug("Ignoring ASGI message type: %s", message_type)
            return

        body_bytes: bytes = message.get("body", b"")
        more_body: bool = message.get("more_body", False)

        if stream_response is None:
            if more_body:
                stream_response = web.StreamResponse(status=response_status)
                _apply_headers(stream_response, response_headers)
                _apply_cors_headers(stream_response, request)
                await stream_response.prepare(request)
                if body_bytes:
                    await stream_response.write(body_bytes)
            else:
                response = web.Response(
                    status=response_status,
                    body=body_bytes,
                    headers=_headers_to_cimultidict(response_headers),
                )
                _apply_cors_headers(response, request)
                if not response_future.done():
                    response_future.set_result(response)

        else:
            if not stream_response.prepared:
                await stream_response.prepare(request)
            if body_bytes:
                await stream_response.write(body_bytes)

        if not more_body:
            disconnect_event.set()
            if stream_response is not None:
                if stream_response.prepared:
                    await stream_response.write_eof()
                if not response_future.done():
                    response_future.set_result(stream_response)
            elif not response_future.done():
                tail_response = web.Response(
                    status=response_status,
                    headers=_headers_to_cimultidict(response_headers),
                )
                _apply_cors_headers(tail_response, request)
                response_future.set_result(tail_response)

    scope = _build_scope(request)

    try:
        await handler(scope, receive, send)
    finally:
        disconnect_event.set()

    if not response_future.done():
        fallback_response = web.Response(
            status=response_status,
            headers=_headers_to_cimultidict(response_headers),
        )
        _apply_cors_headers(fallback_response, request)
        response_future.set_result(fallback_response)

    return await response_future


def _apply_headers(
    response: web.StreamResponse, headers: list[tuple[bytes, bytes]]
) -> None:
    for key, value in headers:
        response.headers[key.decode("latin-1")] = value.decode("latin-1")


def _headers_to_cimultidict(headers: list[tuple[bytes, bytes]]) -> CIMultiDict[str]:
    result: CIMultiDict[str] = CIMultiDict()
    for key, value in headers:
        result.add(key.decode("latin-1"), value.decode("latin-1"))
    return result


def _build_scope(request: web.Request) -> dict[str, Any]:
    http_version = f"{request.version.major}.{request.version.minor}"
    headers: list[tuple[bytes, bytes]] = []
    content_type_present = False
    for name, value in request.headers.items():
        normalized_name = name.lower()
        encoded_name = normalized_name.encode("latin-1")
        encoded_value = value.encode("latin-1")

        if encoded_name == b"content-type":
            if encoded_value:
                content_type_present = True
                headers.append((encoded_name, encoded_value))
            else:
                _LOGGER.debug("Dropping empty Content-Type header from request")
            continue

        headers.append((encoded_name, encoded_value))

    if request.method in {"POST", "PUT", "PATCH"} and not content_type_present:
        headers.append((b"content-type", b"application/json"))
        _LOGGER.debug(
            "Defaulting Content-Type header to application/json for %s %s",
            request.method,
            request.rel_url.path,
        )
    client_host = request.remote
    client: tuple[str, int] | None = None
    if client_host:
        client = (client_host, 0)
    server_info = (
        request.transport.get_extra_info("sockname") if request.transport else None
    )

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": http_version,
        "method": request.method,
        "scheme": request.scheme,
        "path": request.rel_url.path,
        "raw_path": request.raw_path.encode("utf-8"),
        "query_string": request.rel_url.query_string.encode("utf-8"),
        "headers": headers,
        "client": client,
        "server": server_info,
        "root_path": "",
        "app": None,
        "state": {},
    }


def _apply_cors_headers(
    response: web.StreamResponse,
    request: web.Request,
    *,
    origin_override: str | None = None,
    allow_headers: str | None = None,
) -> None:
    """Set CORS headers on the streamable HTTP responses."""

    origin = origin_override or request.headers.get("Origin")
    if not origin:
        return

    response.headers.setdefault("Access-Control-Allow-Origin", origin)
    response.headers.setdefault("Access-Control-Allow-Credentials", "true")

    if allow_headers:
        response.headers.setdefault("Access-Control-Allow-Headers", allow_headers)
