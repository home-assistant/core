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
    """Model Context Protocol Streamable HTTP endpoint."""

    name = f"{DOMAIN}:streamable-http"
    url = STREAMABLE_HTTP_API

    async def get(self, request: web.Request) -> web.StreamResponse:
        """Handle GET requests for streamable HTTP transport."""
        return await self._handle_request(request)

    async def post(self, request: web.Request) -> web.StreamResponse:
        """Handle POST requests for streamable HTTP transport."""
        return await self._handle_request(request)

    async def delete(self, request: web.Request) -> web.StreamResponse:
        """Handle DELETE requests for streamable HTTP transport."""
        return await self._handle_request(request)

    async def _handle_request(self, request: web.Request) -> web.StreamResponse:
        """Handle HTTP requests for streamable transport."""
        # For now, return a simple response
        response = web.Response(
            text="Streamable HTTP transport endpoint",
            status=200,
            headers={"Content-Type": "text/plain"},
        )
        self._add_cors_headers(response, request)
        return response

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
                "Authorization, Content-Type, MCP-Session-ID",
            )
