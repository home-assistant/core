"""Model Context Protocol transport protocol for Streamable HTTP and SSE.

This registers HTTP endpoints that support the Streamable HTTP protocol as
well as the older SSE as a transport layer.

The Streamable HTTP protocol uses a single HTTP endpoint:

- /api/mcp_server: The Streamable HTTP endpoint currently implements the
  stateless protocol for simplicity. This receives client requests and
  sends them to the MCP server, then waits for a response to send back to
  the client.

The older SSE protocol has two HTTP endpoints:

- /mcp_server/sse: The SSE endpoint that is used to establish a session
  with the client and glue to the MCP server. This is used to push responses
  to the client.
- /mcp_server/messages: The endpoint that is used by the client to send
  POST requests with new requests for the MCP server. The request contains
  a session identifier. The response to the client is passed over the SSE
  session started on the other endpoint.

See https://modelcontextprotocol.io/docs/concepts/transports
"""

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound
from aiohttp_sse import sse_response
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import JSONRPCRequest, types
from mcp.server import InitializationOptions, Server
from mcp.shared.message import SessionMessage

from homeassistant.components import conversation
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import llm

from .const import DOMAIN
from .server import create_server
from .session import Session
from .types import MCPServerConfigEntry

_LOGGER = logging.getLogger(__name__)

# Streamable HTTP endpoint
STREAMABLE_API = "/api/mcp"
TIMEOUT = 60  # Seconds

# Content types
CONTENT_TYPE_JSON = "application/json"

# Legacy SSE endpoint
SSE_API = f"/{DOMAIN}/sse"
MESSAGES_API = f"/{DOMAIN}/messages/{{session_id}}"


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    hass.http.register_view(ModelContextProtocolSSEView())
    hass.http.register_view(ModelContextProtocolMessagesView())
    hass.http.register_view(ModelContextProtocolStreamableView())


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


@dataclass
class Streams:
    """Pairs of streams for MCP server communication."""

    # The MCP server reads from the read stream. The HTTP handler receives
    # incoming client messages and writes the to the read_stream_writer.
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]

    # The MCP server writes to the write stream. The HTTP handler reads from
    # the write stream and sends messages to the client.
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]


def create_streams() -> Streams:
    """Create a new pair of streams for MCP server communication."""
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    return Streams(
        read_stream=read_stream,
        read_stream_writer=read_stream_writer,
        write_stream=write_stream,
        write_stream_reader=write_stream_reader,
    )


async def create_mcp_server(
    hass: HomeAssistant, context: Context, entry: MCPServerConfigEntry
) -> tuple[Server, InitializationOptions]:
    """Initialize the MCP server to ensure it's ready to handle requests."""
    llm_context = llm.LLMContext(
        platform=DOMAIN,
        context=context,
        language="*",
        assistant=conversation.DOMAIN,
        device_id=None,
    )
    llm_api_id = entry.data[CONF_LLM_HASS_API]
    server = await create_server(hass, llm_api_id, llm_context)
    options = await hass.async_add_executor_job(
        server.create_initialization_options  # Reads package for version info
    )
    return server, options


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

        server, options = await create_mcp_server(hass, self.context(request), entry)
        streams = create_streams()

        async with (
            sse_response(request) as response,
            session_manager.create(Session(streams.read_stream_writer)) as session_id,
        ):
            session_uri = MESSAGES_API.format(session_id=session_id)
            _LOGGER.debug("Sending SSE endpoint: %s", session_uri)
            await response.send(session_uri, event="endpoint")

            async def sse_reader() -> None:
                """Forward MCP server responses to the client."""
                async for session_message in streams.write_stream_reader:
                    _LOGGER.debug("Sending SSE message: %s", session_message)
                    await response.send(
                        session_message.message.model_dump_json(
                            by_alias=True, exclude_none=True
                        ),
                        event="message",
                    )

            async with anyio.create_task_group() as tg:
                tg.start_soon(sse_reader)
                await server.run(streams.read_stream, streams.write_stream, options)

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


class ModelContextProtocolStreamableView(HomeAssistantView):
    """Model Context Protocol Streamable HTTP endpoint."""

    name = f"{DOMAIN}:streamable"
    url = STREAMABLE_API

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Handle unsupported methods."""
        return web.Response(
            status=HTTPStatus.METHOD_NOT_ALLOWED, text="Only POST method is supported"
        )

    async def post(self, request: web.Request) -> web.StreamResponse:
        """Process JSON-RPC messages for the Model Context Protocol."""
        hass = request.app[KEY_HASS]
        entry = async_get_config_entry(hass)

        # The request must include a JSON-RPC message
        if CONTENT_TYPE_JSON not in request.headers.get("accept", ""):
            raise HTTPBadRequest(text=f"Client must accept {CONTENT_TYPE_JSON}")
        if request.content_type != CONTENT_TYPE_JSON:
            raise HTTPBadRequest(text=f"Content-Type must be {CONTENT_TYPE_JSON}")
        try:
            json_data = await request.json()
            message = types.JSONRPCMessage.model_validate(json_data)
        except ValueError as err:
            _LOGGER.debug("Failed to parse message as JSON-RPC message: %s", err)
            raise HTTPBadRequest(text="Request must be a JSON-RPC message") from err

        _LOGGER.debug("Received client message: %s", message)

        # For notifications and responses only, return 202 Accepted
        if not isinstance(message.root, JSONRPCRequest):
            _LOGGER.debug("Notification or response received, returning 202")
            return web.Response(status=HTTPStatus.ACCEPTED)

        # The MCP server runs as a background task for the duration of the
        # request. We open a buffered stream pair to communicate with it. The
        # request is sent to the MCP server and we wait for a single response
        # then shut down the server.
        server, options = await create_mcp_server(hass, self.context(request), entry)
        streams = create_streams()

        async def run_server() -> None:
            await server.run(
                streams.read_stream, streams.write_stream, options, stateless=True
            )

        async with asyncio.timeout(TIMEOUT), anyio.create_task_group() as tg:
            tg.start_soon(run_server)

            await streams.read_stream_writer.send(SessionMessage(message))
            session_message = await anext(streams.write_stream_reader)
            tg.cancel_scope.cancel()

        _LOGGER.debug("Sending response: %s", session_message)
        return web.json_response(
            data=session_message.message.model_dump(by_alias=True, exclude_none=True),
        )
