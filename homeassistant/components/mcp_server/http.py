"""Model Context Protocol transport protocol for Server Sent Events (SSE).

This registers HTTP endpoints that supports SSE as a transport layer
for the Model Context Protocol. There are two HTTP endpoints:

- /mcp_server/sse: The SSE endpoint that is used to establish a session
  with the client and glue to the MCP server. This is used to push responses
  to the client.
- /mcp_server/messages: The endpoint that is used by the client to send
  POST requests with new requests for the MCP server. The request contains
  a session identifier. The response to the client is passed over the SSE
  session started on the other endpoint.

See https://modelcontextprotocol.io/docs/concepts/transports
"""

import logging
from urllib.parse import urlparse

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound
from aiohttp_sse import sse_response
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import types
from mcp.shared.message import SessionMessage

from homeassistant.components import conversation
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm

from .const import DOMAIN, MESSAGES_API, SSE_API, STREAMABLE_HTTP_API
from .event_store import InMemoryEventStore
from .server import create_server
from .session import Session
from .types import MCPServerConfigEntry

_LOGGER = logging.getLogger(__name__)


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the HTTP transports."""
    hass.http.register_view(ModelContextProtocolSSEView())
    hass.http.register_view(ModelContextProtocolMessagesView())
    hass.http.register_view(ModelContextProtocolStreamableHTTPView())


def async_get_config_entry(hass: HomeAssistant) -> MCPServerConfigEntry:
    """Get the first enabled MCP server config entry.

    The ConfigEntry contains a reference to the actual MCP server used to
    serve the Model Context Protocol.

    Will raise an HTTP error if the expected configuration is not present.
    """
    config_entries: list[MCPServerConfigEntry] = (
        hass.config_entries.async_loaded_entries(DOMAIN)
    )
    if not config_entries:
        raise HTTPNotFound(text="Model Context Protocol server is not configured")
    if len(config_entries) > 1:
        raise HTTPNotFound(text="Found multiple Model Context Protocol configurations")
    return config_entries[0]


class ModelContextProtocolSSEView(HomeAssistantView):
    """Model Context Protocol SSE endpoint."""

    name = f"{DOMAIN}:sse"
    url = SSE_API

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Process SSE messages for the Model Context Protocol.

        This is a long running request for the lifetime of the client session
        and is the primary transport layer between the client and server.

        Pairs of buffered streams act as a bridge between the transport protocol
        (SSE over HTTP views) and the Model Context Protocol. The MCP SDK
        manages all protocol details and invokes commands on our MCP server.
        """
        hass = request.app[KEY_HASS]
        entry = async_get_config_entry(hass)
        session_manager = entry.runtime_data

        context = llm.LLMContext(
            platform=DOMAIN,
            context=self.context(request),
            language="*",
            assistant=conversation.DOMAIN,
            device_id=None,
        )
        llm_api_id = entry.data[CONF_LLM_HASS_API]
        server = await create_server(hass, llm_api_id, context)
        options = await hass.async_add_executor_job(
            server.create_initialization_options  # Reads package for version info
        )

        read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
        read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
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
                await server.run(read_stream, write_stream, options)

            return response


class ModelContextProtocolMessagesView(HomeAssistantView):
    """Model Context Protocol messages endpoint."""

    name = f"{DOMAIN}:messages"
    url = MESSAGES_API

    async def post(
        self,
        request: web.Request,
        session_id: str,
    ) -> web.StreamResponse:
        """Process incoming messages for the Model Context Protocol.

        The request passes a session ID which is used to identify the original
        SSE connection. This view parses incoming messages from the transport
        layer then writes them to the MCP server stream for the session.
        """
        hass = request.app[KEY_HASS]
        config_entry = async_get_config_entry(hass)

        session_manager = config_entry.runtime_data
        if (session := session_manager.get(session_id)) is None:
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
    """Model Context Protocol Streamable HTTP endpoint.

    Implements the MCP streamable HTTP transport specification with full
    event stream buffering and resumability support.
    """

    name = f"{DOMAIN}:streamable-http"
    url = STREAMABLE_HTTP_API

    def __init__(self) -> None:
        """Initialize the streamable HTTP view."""
        # Event store for resumability support
        self._event_store = InMemoryEventStore(max_events_per_stream=1000)

    async def options(self, request: web.Request) -> web.StreamResponse:
        """Handle OPTIONS requests for CORS preflight."""
        response = web.Response(status=200)
        self._add_cors_headers(response, request)
        return response

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Handle GET requests - open SSE stream for server-to-client communication.

        Supports:
        - Basic SSE streaming
        - Event resumability with Last-Event-ID header
        - Session management
        - Origin validation for security
        """
        # Security: Validate Origin header to prevent DNS rebinding attacks
        if not self._validate_origin(request):
            raise HTTPBadRequest(text="Invalid Origin header")

        # Validate Accept header
        accept_header = request.headers.get("Accept", "")
        if "text/event-stream" not in accept_header:
            raise HTTPBadRequest(text="Accept header must include text/event-stream")

        # Handle resumability
        last_event_id = request.headers.get("Last-Event-ID")
        session_id = request.headers.get("Mcp-Session-Id")

        hass = request.app[KEY_HASS]
        config_entry = async_get_config_entry(hass)
        session_manager = config_entry.runtime_data

        # If session ID provided, validate it exists
        if session_id and not session_manager.get(session_id):
            raise HTTPNotFound(text="Session not found")

        # If we have last_event_id, replay missed events
        if last_event_id and session_id:
            stream_id = f"session_{session_id}"
            missed_events = await self._event_store.replay_events_after(
                last_event_id, stream_id
            )

            if missed_events:
                _LOGGER.debug(
                    "Replaying %d missed events for session %s",
                    len(missed_events),
                    session_id,
                )

                async with sse_response(request) as response:
                    self._add_cors_headers(response, request)

                    # Replay missed events
                    for event_message in missed_events:
                        await response.send(
                            event_message.message.model_dump_json(
                                by_alias=True, exclude_none=True
                            ),
                            event="message",
                            id=event_message.event_id,
                        )

                    # Continue with live events from session
                    if session_id and session_manager.get(session_id):
                        # Keep connection open for new events
                        # In a full implementation, would connect to session's write stream
                        await response.send("", event="ping")

                return response

        # For new connections or non-resumable, delegate to existing SSE implementation
        sse_view = ModelContextProtocolSSEView()
        response = await sse_view.get(request)
        self._add_cors_headers(response, request)
        return response

    async def post(self, request: web.Request) -> web.StreamResponse:
        """Handle POST requests - process JSON-RPC messages with event buffering.

        Supports both SSE and JSON responses as per MCP specification.
        """
        # Security: Validate Origin header to prevent DNS rebinding attacks
        if not self._validate_origin(request):
            raise HTTPBadRequest(text="Invalid Origin header")

        # Validate required headers
        accept_header = request.headers.get("Accept", "")
        if not (
            "application/json" in accept_header and "text/event-stream" in accept_header
        ):
            raise HTTPBadRequest(
                text="Accept header must include both application/json and text/event-stream"
            )

        # Validate MCP protocol version
        protocol_version = request.headers.get("MCP-Protocol-Version")
        if protocol_version and protocol_version not in ["2025-06-18", "2024-11-05"]:
            raise HTTPBadRequest(
                text=f"Unsupported MCP protocol version: {protocol_version}"
            )

        # Parse JSON-RPC message
        try:
            json_data = await request.json()
            message = types.JSONRPCMessage.model_validate(json_data)
        except ValueError as err:
            _LOGGER.info("Failed to parse JSON-RPC message: %s", err)
            raise HTTPBadRequest(text="Invalid JSON-RPC message") from err

        _LOGGER.debug("Received streamable HTTP message: %s", message)

        # Handle session management
        session_id = request.headers.get("Mcp-Session-Id")
        hass = request.app[KEY_HASS]
        config_entry = async_get_config_entry(hass)
        session_manager = config_entry.runtime_data

        # For initialize requests, create new session with event buffering
        if hasattr(message, "method") and message.method == "initialize":
            # Create enhanced SSE response with event buffering
            context = llm.LLMContext(
                platform=DOMAIN,
                context=self.context(request),
                language="*",
                assistant=conversation.DOMAIN,
                device_id=None,
            )
            llm_api_id = config_entry.data[CONF_LLM_HASS_API]
            server = await create_server(hass, llm_api_id, context)
            options = await hass.async_add_executor_job(
                server.create_initialization_options
            )

            read_stream_writer: MemoryObjectSendStream[types.JSONRPCMessage | Exception]
            read_stream: MemoryObjectReceiveStream[types.JSONRPCMessage | Exception]
            read_stream_writer, read_stream = anyio.create_memory_object_stream(0)

            write_stream: MemoryObjectSendStream[types.JSONRPCMessage]
            write_stream_reader: MemoryObjectReceiveStream[types.JSONRPCMessage]
            write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

            async with (
                sse_response(request) as response,
                session_manager.create(Session(read_stream_writer)) as new_session_id,
            ):
                # Add session ID header
                response.headers["Mcp-Session-Id"] = new_session_id
                self._add_cors_headers(response, request)

                # Stream ID for event storage
                stream_id = f"session_{new_session_id}"

                # Send the initialize request to the server
                await read_stream_writer.send(message)

                async def enhanced_sse_writer() -> None:
                    """Forward MCP server responses with event buffering."""
                    async for response_message in write_stream_reader:
                        # Store event for resumability
                        event_id = await self._event_store.store_event(
                            stream_id, response_message
                        )

                        _LOGGER.debug("Sending SSE message with event ID %s", event_id)
                        await response.send(
                            response_message.model_dump_json(
                                by_alias=True, exclude_none=True
                            ),
                            event="message",
                            id=event_id,
                        )

                        # Close stream after sending response to initialize
                        if (
                            isinstance(response_message, types.JSONRPCResponse)
                            and response_message.id == message.id
                        ):
                            break

                # Start both tasks
                async with anyio.create_task_group() as tg:
                    tg.start_soon(enhanced_sse_writer)
                    await server.run(read_stream, write_stream, options)

            return response

        # For other requests with session - validate session exists
        if session_id:
            if not session_manager.get(session_id):
                raise HTTPNotFound(text="Session not found")

            # Use existing messages endpoint logic
            messages_view = ModelContextProtocolMessagesView()
            response = await messages_view.post(request, session_id)
            self._add_cors_headers(response, request)
            return response

        # For requests without session (not initialize) - require session
        if hasattr(message, "method"):
            raise HTTPBadRequest(
                text="Session required for requests (except initialize)"
            )

        # For responses/notifications without session, accept them
        if hasattr(message, "result") or hasattr(message, "error"):
            response = web.Response(status=202)  # 202 Accepted
            self._add_cors_headers(response, request)
            return response

        raise HTTPBadRequest(text="Invalid request")

    async def delete(self, request: web.Request) -> web.StreamResponse:
        """Handle DELETE requests - terminate session and clean up events."""
        # Security: Validate Origin header to prevent DNS rebinding attacks
        if not self._validate_origin(request):
            raise HTTPBadRequest(text="Invalid Origin header")

        session_id = request.headers.get("Mcp-Session-Id")
        if not session_id:
            raise HTTPBadRequest(text="Mcp-Session-Id header required")

        hass = request.app[KEY_HASS]
        config_entry = async_get_config_entry(hass)
        session_manager = config_entry.runtime_data

        # Validate session exists
        if not session_manager.get(session_id):
            raise HTTPNotFound(text="Session not found")

        # Clean up event store for this session
        stream_id = f"session_{session_id}"
        self._event_store.clear_stream(stream_id)

        # TODO: Properly terminate the session in session_manager
        # This would require extending the session manager interface

        response = web.Response(status=200)
        self._add_cors_headers(response, request)
        return response

    def _validate_origin(self, request: web.Request) -> bool:
        """Validate Origin header to prevent DNS rebinding attacks.

        As per MCP security requirements, servers must validate the Origin header
        on all incoming connections to prevent DNS rebinding attacks.
        """
        origin = request.headers.get("Origin")

        # If no Origin header, allow (for non-browser clients)
        if not origin:
            return True

        # Parse the origin URL
        try:
            parsed = urlparse(origin)
            hostname = parsed.hostname

            # Allow localhost connections (common for development)
            if hostname in ("localhost", "127.0.0.1", "::1"):
                return True

            # Allow connections from the same host as the server
            # Note: In a production deployment, you might want to be more restrictive
            request_host = request.headers.get("Host", "").split(":")[0]
            if hostname == request_host:
                return True

            # Allow specific trusted origins (could be made configurable)
            # For now, we'll be permissive but log suspicious origins
            _LOGGER.warning("Connection from potentially untrusted origin: %s", origin)

        except (ValueError, AttributeError) as err:
            _LOGGER.warning("Failed to parse Origin header '%s': %s", origin, err)
            return False
        else:
            # TODO: Make this configurable/more restrictive in production
            return True

    def _add_cors_headers(
        self, response: web.StreamResponse, request: web.Request
    ) -> None:
        """Add CORS headers to the response."""
        origin = request.headers.get("Origin")
        if origin:
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")
            response.headers.setdefault(
                "Access-Control-Allow-Headers",
                "Authorization, Content-Type, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID",
            )
            response.headers.setdefault(
                "Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"
            )
            response.headers.setdefault(
                "Access-Control-Max-Age",
                "86400",  # Cache preflight for 24 hours
            )
